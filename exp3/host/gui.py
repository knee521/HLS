"""Tkinter drawing UI. Recognition results come exclusively from FPGA responses."""

import argparse
import logging
import queue
import threading
import tkinter as tk
from datetime import datetime
from tkinter import filedialog, messagebox, ttk

from PIL import Image, ImageDraw, ImageTk
from serial import SerialException
from serial.tools import list_ports

from common.preprocess import image_bytes, preprocess
from common.project import ROOT, configure_logging, read_config
from common.protocol import IMAGE_TYPE, FrameDecoder, image_frame
from host.client import SerialClient
from host.measurements import append_csv, make_row, release_metadata


class Application:
    def __init__(self, window: tk.Tk, config: dict) -> None:
        self.window, self.config = window, config
        self.client: SerialClient | None = None
        self.busy = False
        self.closing = False
        self.loaded_pixels: bytes | None = None
        self.previous: tuple[int, int] | None = None
        self.image = Image.new("L", (28, 28))
        self.events: queue.Queue = queue.Queue()
        self.run_id = datetime.now().strftime("handwriting_%Y%m%d_%H%M%S_%f")
        self.output = ROOT / "evidence/board" / self.run_id
        self.total = self.correct = self.labeled = 0
        window.title("实验三 FPGA 手写数字识别")
        window.resizable(False, False)
        window.protocol("WM_DELETE_WINDOW", self.close)
        frame = ttk.Frame(window, padding=16)
        frame.grid()
        ttk.Label(frame, text="串口").grid(row=0, column=0, sticky="w")
        self.port = ttk.Combobox(frame, width=16, values=[p.device for p in list_ports.comports()])
        self.port.grid(row=0, column=1, sticky="w")
        self.baud = ttk.Combobox(
            frame, values=[115200, 230400, 460800, 921600], width=12, state="readonly"
        )
        self.baud.set(str(config["baud"]))
        self.baud.grid(row=0, column=2)
        self.connection = ttk.Button(frame, text="连接", command=self.connect)
        self.connection.grid(row=0, column=3)
        ttk.Label(frame, text="在黑色画板上书写一个数字").grid(
            row=1, column=0, columnspan=2, pady=8
        )
        ttk.Label(frame, text="实际发送的 28×28 图像").grid(row=1, column=2, columnspan=2, pady=8)
        self.canvas = tk.Canvas(
            frame, width=280, height=280, background="black", highlightthickness=1
        )
        self.canvas.grid(row=2, column=0, columnspan=2, padx=(0, 12))
        self.preview = ttk.Label(frame)
        self.preview.grid(row=2, column=2, columnspan=2)
        self.canvas.bind("<Button-1>", self.draw)
        self.canvas.bind("<B1-Motion>", self.draw)
        self.canvas.bind("<ButtonRelease-1>", lambda _: setattr(self, "previous", None))
        ttk.Button(frame, text="清空", command=self.clear).grid(row=3, column=0, pady=10)
        ttk.Button(frame, text="载入文件", command=self.load).grid(row=3, column=1)
        ttk.Button(frame, text="保存图像或帧", command=self.save).grid(row=3, column=2)
        self.send_button = ttk.Button(frame, text="发送识别", command=self.send)
        self.send_button.grid(row=3, column=3)
        ttk.Label(frame, text="真实数字（可选）").grid(row=4, column=0, columnspan=2, sticky="w")
        self.label = ttk.Combobox(frame, values=[""] + list(range(10)), width=8, state="readonly")
        self.label.set("")
        self.label.grid(row=4, column=2, sticky="w")
        self.result = tk.StringVar(value="FPGA 结果：—")
        ttk.Label(frame, textvariable=self.result, font=("Microsoft YaHei", 18)).grid(
            row=5, column=0, columnspan=4, sticky="w", pady=(12, 4)
        )
        self.status = tk.StringVar(value="请先选择开发板串口，并确认波特率与下载的程序一致。")
        ttk.Label(frame, textvariable=self.status, wraplength=570).grid(
            row=6, column=0, columnspan=4, sticky="w"
        )
        self.statistics = tk.StringVar(value="已发送 0 次；未标注的样本不计入准确率。")
        ttk.Label(frame, textvariable=self.statistics).grid(
            row=7, column=0, columnspan=4, sticky="w", pady=8
        )
        self.render()
        self.window.after(25, self.poll)

    def render(self, processed: Image.Image | None = None) -> None:
        self.draw_photo = ImageTk.PhotoImage(
            self.image.resize((280, 280), Image.Resampling.NEAREST)
        )
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, image=self.draw_photo, anchor="nw")
        preview = processed if processed is not None else Image.new("L", (28, 28))
        self.preview_photo = ImageTk.PhotoImage(
            preview.resize((280, 280), Image.Resampling.NEAREST)
        )
        self.preview.configure(image=self.preview_photo)

    def draw(self, event) -> None:
        if self.busy:
            return
        point = (max(0, min(27, event.x // 10)), max(0, min(27, event.y // 10)))
        brush = ImageDraw.Draw(self.image)
        if self.previous is None:
            brush.ellipse(
                (point[0], point[1], min(27, point[0] + 1), min(27, point[1] + 1)), fill=255
            )
        else:
            brush.line((self.previous, point), fill=255, width=2)
        self.previous = point
        self.loaded_pixels = None
        self.render()

    def clear(self) -> None:
        if not self.busy:
            self.image = Image.new("L", (28, 28))
            self.loaded_pixels = None
            self.previous = None
            self.render()

    def prepare(self) -> bytes:
        processed = (
            Image.frombytes("L", (28, 28), self.loaded_pixels)
            if self.loaded_pixels is not None
            else preprocess(self.image)
        )
        self.render(processed)
        return image_bytes(processed)

    def connect(self) -> None:
        if self.busy:
            return
        try:
            if self.client:
                self.client.close()
                self.client = None
                self.connection.configure(text="连接")
                self.port.configure(state="normal")
                self.baud.configure(state="readonly")
                self.status.set("已断开连接。")
            else:
                if not self.port.get():
                    raise ValueError("请选择开发板对应的 COM 端口。")
                self.client = SerialClient.connect(
                    self.port.get(), int(self.baud.get()), self.config["request_timeout_s"]
                )
                self.connection.configure(text="断开")
                self.port.configure(state="disabled")
                self.baud.configure(state="disabled")
                self.status.set(f"已连接 {self.port.get()}，{self.baud.get()} 波特率。")
        except (OSError, SerialException, ValueError) as exc:
            messagebox.showerror("连接失败", str(exc))

    def load(self) -> None:
        if self.busy:
            return
        path = filedialog.askopenfilename(filetypes=[("图像或数据", "*.png *.bin *.frame")])
        if not path:
            return
        try:
            from pathlib import Path

            selected = Path(path)
            if selected.suffix.lower() == ".frame":
                raw = selected.read_bytes()
                frames = FrameDecoder().feed(raw)
                if len(frames) != 1 or frames[0].kind != IMAGE_TYPE or frames[0].encode() != raw:
                    raise ValueError("文件不是一个完整、有效的图像请求帧。")
                pixels = frames[0].payload
            elif selected.suffix.lower() == ".bin":
                pixels = selected.read_bytes()
                if len(pixels) != 784:
                    raise ValueError("图像二进制文件必须恰好为784字节。")
            else:
                with Image.open(selected) as image:
                    pixels = image_bytes(preprocess(image))
            self.image = Image.frombytes("L", (28, 28), pixels)
            self.loaded_pixels = pixels
            self.render(self.image)
        except (OSError, ValueError) as exc:
            messagebox.showerror("载入失败", str(exc))

    def save(self) -> None:
        try:
            pixels = self.prepare()
            path = filedialog.asksaveasfilename(
                defaultextension=".bin",
                filetypes=[
                    ("784字节图像", "*.bin"),
                    ("完整请求帧", "*.frame"),
                    ("灰度图片", "*.png"),
                ],
            )
            if path:
                from pathlib import Path

                selected = Path(path)
                if selected.suffix.lower() == ".png":
                    Image.frombytes("L", (28, 28), pixels).save(selected)
                else:
                    selected.write_bytes(
                        image_frame(pixels, 0) if selected.suffix == ".frame" else pixels
                    )
        except (OSError, ValueError) as exc:
            messagebox.showerror("保存失败", str(exc))

    def send(self) -> None:
        if self.busy:
            return
        if self.client is None:
            messagebox.showinfo("尚未连接", "请先连接开发板串口。")
            return
        try:
            pixels = self.prepare()
        except ValueError as exc:
            messagebox.showinfo("请先书写", str(exc))
            return
        label = self.label.get()
        baud = int(self.baud.get())
        client = self.client
        self.busy = True
        self.send_button.configure(state="disabled")
        self.connection.configure(state="disabled")
        self.status.set("等待 FPGA 返回结果…")

        def worker() -> None:
            try:
                self.output.mkdir(parents=True, exist_ok=True)
                sample_id = self.total
                stem = self.output / f"sample_{sample_id:04d}"
                stem.with_suffix(".bin").write_bytes(pixels)
                stem.with_suffix(".frame").write_bytes(image_frame(pixels, client.sequence))
                Image.frombytes("L", (28, 28), pixels).save(stem.with_suffix(".png"))
                measurement = client.request(pixels)
                row = make_row(
                    measurement,
                    pixels=pixels,
                    run_id=self.run_id,
                    config_id=self.config["config_id"],
                    baud=baud,
                    sample_id=sample_id,
                    source="handwriting",
                    label=label,
                    metadata=release_metadata(None),
                )
                append_csv(self.output / "transactions.csv", row)
                self.events.put(("result", row))
            except Exception as exc:
                logging.exception("GUI worker failed")
                self.events.put(("error", str(exc)))

        threading.Thread(target=worker, daemon=True).start()

    def poll(self) -> None:
        try:
            kind, value = self.events.get_nowait()
        except queue.Empty:
            pass
        else:
            self.busy = False
            self.send_button.configure(state="normal")
            self.connection.configure(state="normal")
            if kind == "result":
                self.total += 1
                if value["label"] != "":
                    self.labeled += 1
                    self.correct += int(
                        value["status"] == "ok" and value["prediction"] == int(value["label"])
                    )
                if value["status"] == "ok":
                    self.result.set(
                        f"FPGA 结果：{value['prediction']}    {value['total_ms']:.2f} ms"
                    )
                    self.status.set(
                        f"序号 {value['seq']}；核心 {value['inference_cycles']} 周期；记录已保存。"
                    )
                else:
                    self.result.set("本次识别失败")
                    self.status.set(value["error_reason"])
                self.statistics.set(
                    f"已发送 {self.total} 次；已标注 {self.labeled} 次，正确 {self.correct} 次。"
                )
            else:
                self.status.set(f"操作失败：{value}")
        if self.closing and not self.busy:
            self.close()
        else:
            self.window.after(25, self.poll)

    def close(self) -> None:
        if self.busy:
            self.closing = True
            return
        if self.client:
            self.client.close()
        self.window.destroy()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="configs/baseline.json")
    parser.add_argument(
        "--smoke-test", action="store_true", help="Verify GUI without opening hardware"
    )
    args = parser.parse_args()
    configure_logging()
    window = tk.Tk()
    if args.smoke_test:
        window.withdraw()
    app = Application(window, read_config(args.config))
    if args.smoke_test:
        ImageDraw.Draw(app.image).line((13, 5, 13, 23), fill=255, width=2)
        assert len(app.prepare()) == 784
        window.after(50, app.close)
    window.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
