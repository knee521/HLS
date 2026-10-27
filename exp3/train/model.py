"""The only floating-point architecture used by training and export."""

import torch
from torch import nn
from torchvision.datasets import MNIST

from common.project import ROOT


class MLP(nn.Module):
    def __init__(self) -> None:
        super().__init__()
        self.fc1 = nn.Linear(784, 32)
        self.fc2 = nn.Linear(32, 10)

    def forward(self, pixels: torch.Tensor) -> torch.Tensor:
        x = pixels.reshape(-1, 784).float() / 256.0
        return self.fc2(torch.relu(self.fc1(x)))


def dataset(training: bool) -> tuple[torch.Tensor, torch.Tensor]:
    data = MNIST(str(ROOT / "data" / "mnist"), train=training, download=True)
    return data.data.reshape(-1, 784), data.targets


def load_model() -> MLP:
    model = MLP()
    checkpoint = torch.load(ROOT / "model" / "best.pt", map_location="cpu", weights_only=True)
    model.load_state_dict(checkpoint["state_dict"])
    model.eval()
    return model


@torch.inference_mode()
def float_predictions(model: MLP, pixels: torch.Tensor) -> torch.Tensor:
    return torch.cat([model(chunk).argmax(1) for chunk in pixels.split(1024)])
