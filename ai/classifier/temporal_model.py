import logging
from typing import Any, Dict, Optional

import torch
import torch.nn as nn
import torch.nn.functional as F

logger = logging.getLogger("PoseSequenceClassifier")


class TemporalAttention(nn.Module):
    """
    Self-attention pooling layer over temporal hidden states.
    Computes a learned weighted sum of sequence states to emphasize key motion frames.
    """

    def __init__(self, hidden_dim: int):
        super().__init__()
        self.projection = nn.Sequential(
            nn.Linear(hidden_dim, hidden_dim // 2),
            nn.Tanh(),
            nn.Linear(hidden_dim // 2, 1, bias=False),
        )

    def forward(self, hidden_states: torch.Tensor) -> torch.Tensor:
        """
        Args:
            hidden_states: (batch_size, seq_len, hidden_dim)

        Returns:
            pooled: (batch_size, hidden_dim)
        """
        # attention_scores: (batch_size, seq_len, 1)
        scores = self.projection(hidden_states)
        weights = F.softmax(scores, dim=1)
        # weighted sum: (batch_size, hidden_dim)
        pooled = torch.sum(weights * hidden_states, dim=1)
        return pooled


class PoseSequenceClassifier(nn.Module):
    """
    Lightweight, real-time temporal deep learning classifier for exercise recognition.
    
    Supports LSTM and GRU recurrent architectures with self-attention temporal pooling,
    batch normalization, dropout regularization, and linear classification head.

    Input shape: (batch_size, sequence_length, input_size)
    Output shape: (batch_size, num_classes) logits
    """

    def __init__(
        self,
        input_size: int = 73,
        hidden_size: int = 64,
        num_layers: int = 2,
        num_classes: int = 6,
        rnn_type: str = "lstm",
        bidirectional: bool = True,
        dropout: float = 0.2,
        sequence_length: Optional[int] = 30,
    ):
        super().__init__()
        self.input_size = input_size
        self.hidden_size = hidden_size
        self.num_layers = num_layers
        self.num_classes = num_classes
        self.rnn_type = rnn_type.lower()
        self.bidirectional = bidirectional
        self.dropout_rate = dropout
        self.sequence_length = sequence_length

        if self.rnn_type not in ["lstm", "gru"]:
            raise ValueError(f"Unsupported rnn_type: '{self.rnn_type}'. Choose 'lstm' or 'gru'.")

        # Input feature normalization
        self.input_norm = nn.LayerNorm(input_size)
        self.input_dropout = nn.Dropout(p=dropout)

        # Recurrent temporal backbone
        rnn_dropout = dropout if num_layers > 1 else 0.0
        rnn_kwargs = {
            "input_size": input_size,
            "hidden_size": hidden_size,
            "num_layers": num_layers,
            "batch_first": True,
            "bidirectional": bidirectional,
            "dropout": rnn_dropout,
        }

        if self.rnn_type == "lstm":
            self.rnn = nn.LSTM(**rnn_kwargs)
        else:
            self.rnn = nn.GRU(**rnn_kwargs)

        rnn_out_dim = hidden_size * (2 if bidirectional else 1)

        # Temporal aggregation: Self-attention pooling
        self.attention = TemporalAttention(hidden_dim=rnn_out_dim)

        # Classification Head: combine attention representation + last hidden state
        combined_dim = rnn_out_dim * 2
        self.classifier = nn.Sequential(
            nn.Linear(combined_dim, hidden_size),
            nn.LayerNorm(hidden_size),
            nn.GELU(),
            nn.Dropout(p=dropout),
            nn.Linear(hidden_size, num_classes),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Forward pass.

        Args:
            x: Tensor of shape (batch_size, sequence_length, input_size)

        Returns:
            logits: Tensor of shape (batch_size, num_classes)
        """
        # Ensure 3D input shape
        if x.dim() == 2:
            x = x.unsqueeze(0)

        # Layer norm and input dropout
        norm_x = self.input_dropout(self.input_norm(x))

        # Recurrent forward
        if self.rnn_type == "lstm":
            rnn_out, (h_n, _) = self.rnn(norm_x)
        else:
            rnn_out, h_n = self.rnn(norm_x)

        # 1. Attention-pooled temporal representation: (batch_size, rnn_out_dim)
        attn_rep = self.attention(rnn_out)

        # 2. Last time-step representation: (batch_size, rnn_out_dim)
        last_step = rnn_out[:, -1, :]

        # Combined temporal representation: (batch_size, combined_dim)
        combined = torch.cat([attn_rep, last_step], dim=1)

        # Classification logits: (batch_size, num_classes)
        logits = self.classifier(combined)
        return logits

    def predict_proba(self, x: torch.Tensor) -> torch.Tensor:
        """
        Computes calibrated class probabilities via softmax.

        Args:
            x: Tensor of shape (batch_size, sequence_length, input_size)

        Returns:
            probabilities: Tensor of shape (batch_size, num_classes)
        """
        logits = self.forward(x)
        return F.softmax(logits, dim=-1)

    def get_num_parameters(self) -> int:
        """Returns total number of trainable model parameters."""
        return sum(p.numel() for p in self.parameters() if p.requires_grad)

    def get_model_size_kb(self) -> float:
        """Estimates model parameter memory footprint in kilobytes."""
        param_bytes = sum(p.numel() * p.element_size() for p in self.parameters())
        buffer_bytes = sum(b.numel() * b.element_size() for b in self.buffers())
        return (param_bytes + buffer_bytes) / 1024.0

    def to_config(self) -> Dict[str, Any]:
        """Serializes architecture hyperparameters to dictionary."""
        return {
            "input_size": self.input_size,
            "hidden_size": self.hidden_size,
            "num_layers": self.num_layers,
            "num_classes": self.num_classes,
            "rnn_type": self.rnn_type,
            "bidirectional": self.bidirectional,
            "dropout": self.dropout_rate,
            "sequence_length": self.sequence_length,
            "num_parameters": self.get_num_parameters(),
        }

    @classmethod
    def from_config(cls, config: Dict[str, Any]) -> "PoseSequenceClassifier":
        """Instantiates model architecture from config dictionary."""
        return cls(
            input_size=config.get("input_size", 73),
            hidden_size=config.get("hidden_size", 64),
            num_layers=config.get("num_layers", 2),
            num_classes=config.get("num_classes", 6),
            rnn_type=config.get("rnn_type", "lstm"),
            bidirectional=config.get("bidirectional", True),
            dropout=config.get("dropout", 0.2),
            sequence_length=config.get("sequence_length", 30),
        )
