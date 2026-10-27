"""Train on 55k MNIST samples and select checkpoint only on 5k validation samples."""

import argparse
import csv
import logging
import random
import time

import numpy as np
import torch
from torch import nn

from common.project import ROOT, configure_logging, read_config, sha256, write_json
from train.model import MLP, dataset, float_predictions


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="configs/baseline.json")
    args = parser.parse_args()
    configure_logging()
    config = read_config(args.config)
    seed = config["seed"]
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.set_num_threads(config["cpu_threads"])
    torch.use_deterministic_algorithms(True)
    pixels, labels = dataset(True)
    if len(pixels) != config["train_size"] + config["validation_size"]:
        raise ValueError("Unexpected MNIST training set size")
    indices = torch.randperm(len(pixels), generator=torch.Generator().manual_seed(seed))
    training = indices[: config["train_size"]]
    validation = indices[config["train_size"] :]
    (ROOT / "model").mkdir(exist_ok=True)
    np.savez(
        ROOT / "model" / "split_indices.npz",
        train=training.numpy(),
        validation=validation.numpy(),
        calibration=training[: config["calibration_size"]].numpy(),
    )
    model = MLP()
    optimizer = torch.optim.Adam(model.parameters(), lr=config["learning_rate"])
    criterion = nn.CrossEntropyLoss()
    shuffle = torch.Generator().manual_seed(seed + 1)
    folder = ROOT / "evidence" / "training"
    folder.mkdir(parents=True, exist_ok=True)
    best = -1.0
    best_epoch = 0
    started = time.perf_counter()
    with (folder / "epochs.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=["epoch", "loss", "train_accuracy", "validation_accuracy", "elapsed_s"],
        )
        writer.writeheader()
        for epoch in range(1, config["epochs"] + 1):
            model.train()
            order = training[torch.randperm(len(training), generator=shuffle)]
            loss_sum = 0.0
            correct = 0
            for batch in order.split(config["batch_size"]):
                optimizer.zero_grad(set_to_none=True)
                logits = model(pixels[batch])
                loss = criterion(logits, labels[batch])
                loss.backward()
                optimizer.step()
                loss_sum += loss.item() * len(batch)
                correct += int((logits.argmax(1) == labels[batch]).sum())
            model.eval()
            accuracy = float(
                (float_predictions(model, pixels[validation]) == labels[validation]).double().mean()
            )
            row = {
                "epoch": epoch,
                "loss": loss_sum / len(training),
                "train_accuracy": correct / len(training),
                "validation_accuracy": accuracy,
                "elapsed_s": time.perf_counter() - started,
            }
            writer.writerow(row)
            stream.flush()
            logging.info(
                "epoch=%d loss=%.5f train=%.4f validation=%.4f",
                epoch,
                row["loss"],
                row["train_accuracy"],
                accuracy,
            )
            if accuracy > best:
                best, best_epoch = accuracy, epoch
                torch.save(
                    {
                        "state_dict": model.state_dict(),
                        "epoch": epoch,
                        "validation_accuracy": accuracy,
                        "config": config,
                    },
                    ROOT / "model" / "best.pt",
                )
    write_json(
        folder / "training_summary.json",
        {
            "config": config,
            "best_epoch": best_epoch,
            "best_validation_accuracy": best,
            "model_sha256": sha256("model/best.pt"),
            "split_sha256": sha256("model/split_indices.npz"),
            "test_set_used_for_selection": False,
            "elapsed_s": time.perf_counter() - started,
            "data_files": {
                str(p.relative_to(ROOT)): sha256(p) for p in (ROOT / "data/mnist").rglob("*.gz")
            },
        },
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
