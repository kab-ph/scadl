import sys
from pathlib import Path

import h5py
import keras
import numpy as np
from keras.layers import Conv1D, Dense, Flatten, Input, MaxPooling1D
from keras.models import Sequential

from scadl.augmentation import Mixup, RandomCrop
from scadl.profile import Profile
from scadl.tools import normalization, remove_avg, sbox


def leakage_model(data):
    """leakage model for sbox[2]"""
    return sbox[data["plaintext"][2] ^ data["key"][2]]


def aug_mixup(x: np.ndarray, y: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Data augmentation based on mixup"""
    mix = Mixup()
    x, y = mix.generate(x_train=x, y_train=y, ratio=1, alpha=1)
    return x, y


def aug_crop(x: np.ndarray, y: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Data augmentation based on random crop"""
    mix = RandomCrop()
    x, y = mix.generate(x_train=x, y_train=y, ratio=1, window=5)
    return x, y


def mlp_short(len_samples: int) -> keras.Model:
    model = Sequential()
    model.add(Input(shape=(len_samples,)))
    model.add(Dense(20, activation="relu"))
    # BatchNormalization()
    model.add(Dense(50, activation="relu"))
    model.add(Dense(256, activation="softmax"))
    model.compile(
        loss="categorical_crossentropy",
        optimizer="adam",
        metrics=["accuracy"],
    )
    return model


def model_cnn(sample_len: int, range_outer_layer: int) -> keras.Model:
    model = Sequential()
    model.add(Input(shape=(sample_len, 1)))
    model.add(
        Conv1D(
            filters=8,
            kernel_size=32,
            padding="same",
            activation="relu",
        )
    )
    model.add(MaxPooling1D(pool_size=3))
    model.add(
        Conv1D(
            filters=8,
            kernel_size=16,
            padding="same",
            activation="tanh",
        )
    )
    model.add(MaxPooling1D(pool_size=3))
    model.add(
        Conv1D(
            filters=8,
            kernel_size=8,
            padding="same",
            activation="tanh",
        )
    )
    model.add(MaxPooling1D(pool_size=2))
    model.add(Flatten())
    model.add(Dense(50, activation="relu"))
    model.add(Dense(range_outer_layer, activation="softmax"))
    model.compile(
        optimizer="adam", loss="categorical_crossentropy", metrics=["accuracy"]
    )
    return model


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Need to specify the location of training data and model")
        exit()
    dataset_dir = Path(sys.argv[1])

    # Load traces and metadata for training
    file = h5py.File(dataset_dir / "ASCAD.h5", "r")
    leakages = file["Profiling_traces"]["traces"][:]
    metadata = file["Profiling_traces"]["metadata"][:]

    # Select POIs where SNR is high
    poi = (
        leakages  # np.concatenate((leakages[:, 515:520], leakages[:, 148:158]), axis=1)
    )

    # Preprocess traces
    x_train = normalization(remove_avg(poi), feature_range=(-1, 1))
    GUESS_RANGE = 256

    # Build the model
    if sys.argv[2] == "mlp":
        model = mlp_short(x_train.shape[1])
    elif sys.argv[2] == "cnn":
        model = model_cnn(x_train.shape[1], GUESS_RANGE)
    else:
        print("Invalid model type")
        exit()

    model.summary()

    # Train the model
    profile_engine = Profile(model, leakage_model=leakage_model)
    profile_engine.data_augmentation(aug_mixup)
    profile_engine.train(
        x_train=x_train,
        metadata=metadata,
        guess_range=256,
        epochs=50,
        batch_size=128,
        validation_split=0.1,
        data_augmentation=False,
    )

    profile_engine.save_model("model.keras")
