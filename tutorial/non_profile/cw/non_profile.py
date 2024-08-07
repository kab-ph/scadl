import sys
import matplotlib.pyplot as plt
import numpy as np
from tqdm import tqdm
import tensorflow as tf
from keras.models import Sequential
from keras.layers import Conv1D, MaxPooling1D, Dense, Flatten
from scadl.non_profile import NonProfile
from scadl.tools import sbox, normalization, remove_avg


TARGET_BYTE = 0


def mlp_non_profiling(len_smaples):
    """It retrurns an MLP model"""
    model = Sequential()
    model.add(Dense(20, input_dim=len_smaples, activation=tf.nn.relu))
    model.add(Dense(10, activation=tf.nn.relu))
    model.add(Dense(2, activation=tf.nn.softmax))
    model.compile(optimizer="adam", loss="mean_squared_error", metrics=["accuracy"])
    return model


def leakage_model(data, guess):
    """It returns the leakage function"""
    return 1 & ((sbox[data["plaintext"][TARGET_BYTE] ^ guess]))  # lsb


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Need to specify the location of training data")
        exit()

    DIR = sys.argv[1]
    leakages = np.load(DIR + "/test/traces.npy")[0:3000]
    metadata = np.load(DIR + "/test/combined_test.npy")[0:3000]
    correct_key = metadata["key"][0][0]

    """Subtracting average from traces + normalization"""
    avg = remove_avg(leakages[:, 1315:1325])
    x_train = normalization(avg, feature_range=(0, 1)) 

    """Selecting the model"""
    model_dl = mlp_non_profiling(x_train.shape[1])

    """Non-profiling DL"""
    EPOCHS = 50
    key_range = range(0, 256)
    acc = np.zeros((len(key_range), EPOCHS))
    profile_engine = NonProfile(leakage_model=leakage_model)
    for index, guess in enumerate(tqdm(key_range)):
        acc[index] = profile_engine.train(
            model=mlp_non_profiling(x_train.shape[1]),
            x_train=x_train,
            metadata=metadata,
            guess=guess,
            hist_acc="accuracy",
            num_classes=2,
            epochs=EPOCHS,
            batch_size=1000,
        )
    guessed_key = np.argmax(np.max(acc, axis=1))
    print(f"guessed key = {guessed_key}")
    plt.plot(acc.T, "grey")
    plt.plot(acc[correct_key], "black")
    plt.xlabel("Number of epochs")
    plt.ylabel("Accuracy ")
    plt.show()
