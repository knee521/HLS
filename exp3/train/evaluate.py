"""Final frozen-model evaluation; also exports exactly the same bytes for HLS testing."""

import argparse
import csv

import numpy as np
import torch
from PIL import Image

from common.preprocess import preprocess
from common.project import ROOT, read_config, sha256, write_json
from train.export_quant import load_quantized
from train.model import dataset, float_predictions, load_model


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="configs/baseline.json")
    parser.add_argument("--split", choices=["test"], default="test")
    args = parser.parse_args()
    config = read_config(args.config)
    torch.set_num_threads(config["cpu_threads"])
    pixels, labels_t = dataset(False)
    labels = labels_t.numpy()
    if len(labels) != 10000:
        raise ValueError("The formal test must contain exactly 10000 examples")
    floating = float_predictions(load_model(), pixels).numpy()
    quantized = load_quantized()
    fixed, scores, _, saturated = quantized.infer(pixels.numpy())
    fp_acc, q_acc = float((floating == labels).mean()), float((fixed == labels).mean())
    loss = max(0.0, fp_acc - q_acc)
    passed = (
        fp_acc >= config["float_accuracy_min"]
        and q_acc >= config["fixed_accuracy_min"]
        and loss < config["absolute_accuracy_loss_max"]
        and loss / fp_acc < config["relative_accuracy_loss_max"]
    )
    folder = ROOT / "evidence/training"
    folder.mkdir(parents=True, exist_ok=True)
    with (folder / "test_predictions.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(
            ["sample_id", "label", "float_prediction", "fixed_prediction"]
            + [f"score_{i}" for i in range(10)]
        )
        for i in range(10000):
            writer.writerow([i, labels[i], floating[i], fixed[i], *scores[i]])
    confusion = np.zeros((10, 10), dtype=np.int64)
    np.add.at(confusion, (labels, fixed), 1)
    np.savetxt(folder / "confusion_matrix.csv", confusion, delimiter=",", fmt="%d")
    vectors = ROOT / "data/vectors"
    vectors.mkdir(parents=True, exist_ok=True)
    pixels.numpy().astype("u1").tofile(vectors / "test_images.bin")
    labels.astype("u1").tofile(vectors / "test_labels.bin")
    scores.astype("<i4").tofile(vectors / "test_scores.bin")
    # Two deterministic examples of every class and four numerical boundary images.
    selected = np.array(
        [int(i) for digit in range(10) for i in np.flatnonzero(labels == digit)[:2]]
    )
    boundary = np.vstack(
        [np.zeros(784), np.full(784, 255), np.arange(784) % 2 * 255, np.eye(28).reshape(-1) * 255]
    ).astype("u1")
    cosim_pixels = np.vstack([pixels.numpy()[selected], boundary])
    cosim_predictions, cosim_scores, _, _ = quantized.infer(cosim_pixels)
    cosim_pixels.tofile(vectors / "cosim_images.bin")
    cosim_scores.astype("<i4").tofile(vectors / "cosim_scores.bin")
    cosim_predictions.astype("u1").tofile(vectors / "cosim_labels.bin")
    (vectors / "cosim_predictions.hex").write_text(
        "\n".join(f"{int(value):02x}" for value in cosim_predictions) + "\n", encoding="ascii"
    )
    for index, image in enumerate(cosim_pixels):
        (vectors / f"sample_{index:02d}.hex").write_text(
            "\n".join(f"{int(value):02x}" for value in image) + "\n", encoding="ascii"
        )
    # Separate diagnostic: never substitute this geometrically transformed set for MNIST.
    transformed = np.stack(
        [
            np.asarray(preprocess(Image.fromarray(p.reshape(28, 28)))).reshape(-1)
            for p in pixels.numpy()
        ]
    )
    transformed_prediction, _, _, _ = quantized.infer(transformed)
    write_json(
        folder / "evaluation.json",
        {
            "samples": 10000,
            "float_accuracy": fp_acc,
            "fixed_accuracy": q_acc,
            "absolute_loss": loss,
            "relative_loss": loss / fp_acc,
            "passed": passed,
            "saturated_activations": saturated,
            "saturation_fraction": saturated / 320000,
            "gui_geometry_diagnostic_accuracy": float((transformed_prediction == labels).mean()),
            "model_sha256": sha256("model/best.pt"),
            "quantized_sha256": sha256("model/quantized.npz"),
            "cosim_sample_ids": selected.tolist(),
            "cosim_predictions": cosim_predictions.tolist(),
            "test_images_sha256": sha256(vectors / "test_images.bin"),
            "test_scores_sha256": sha256(vectors / "test_scores.bin"),
        },
    )
    print(f"float={fp_acc:.4%} fixed={q_acc:.4%} relative_loss={loss / fp_acc:.5%} pass={passed}")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
