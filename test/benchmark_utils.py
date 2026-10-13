# SPDX-FileCopyrightText: © 2026 Ivan
# SPDX-License-Identifier: Apache-2.0


# Just includes Ridge regression, metrics (MSE, R2, accuracy), and synthetic data generators.


import math
import random

def train_ridge(X_train, y_train, l2_reg=1.0):
    """
    Fits w for y = X_aug * w with L2 regularization on non-bias weights.
    Returns weights list of length D (index 0 is bias).
    """
    N = len(X_train)
    if N == 0:
        return [0.0]
    D = len(X_train[0]) + 1
    
    X_aug = [[1.0] + [float(v) for v in row] for row in X_train]
    
    # A = X^T X + lambda * I
    A = [[0.0] * D for _ in range(D)]
    for i in range(D):
        for j in range(D):
            A[i][j] = sum(X_aug[k][i] * X_aug[k][j] for k in range(N))
            if i == j and i > 0:
                A[i][j] += l2_reg
                
    b = [sum(X_aug[k][i] * float(y_train[k]) for k in range(N)) for i in range(D)]
    
    # Gaussian elimination with partial pivoting
    for col in range(D):
        max_r = max(range(col, D), key=lambda r: abs(A[r][col]))
        A[col], A[max_r] = A[max_r], A[col]
        b[col], b[max_r] = b[max_r], b[col]
        
        pivot = A[col][col]
        if abs(pivot) < 1e-12:
            continue
        for row in range(col + 1, D):
            f = A[row][col] / pivot
            for c in range(col, D):
                A[row][c] -= f * A[col][c]
            b[row] -= f * b[col]
            
    # Back-substitution
    w = [0.0] * D
    for row in range(D - 1, -1, -1):
        if abs(A[row][row]) > 1e-12:
            w[row] = (b[row] - sum(A[row][c] * w[c] for c in range(row + 1, D))) / A[row][row]
            
    return w

def predict_linear(w, X_sample):
    return w[0] + sum(w[i + 1] * float(X_sample[i]) for i in range(len(X_sample)))

def predict_binary(w, X_sample, threshold=0.5):
    return 1 if predict_linear(w, X_sample) >= threshold else 0

def calc_mse(y_true, y_pred):
    if len(y_true) == 0:
        return 0.0
    return sum((t - p) ** 2 for t, p in zip(y_true, y_pred)) / len(y_true)

def calc_r2(y_true, y_pred):
    if len(y_true) == 0:
        return 0.0
    mean_y = sum(y_true) / len(y_true)
    ss_tot = sum((y - mean_y) ** 2 for y in y_true)
    if ss_tot < 1e-9:
        return 1.0
    ss_res = sum((y - p) ** 2 for y, p in zip(y_true, y_pred))
    return 1.0 - (ss_res / ss_tot)

def calc_accuracy(y_true, y_pred):
    if len(y_true) == 0:
        return 0.0
    correct = sum(1 for t, p in zip(y_true, y_pred) if t == p)
    return (correct / len(y_true)) * 100.0

def cosine_similarity(v1, v2):
    dot = sum(a * b for a, b in zip(v1, v2))
    norm1 = math.sqrt(sum(a * a for a in v1))
    norm2 = math.sqrt(sum(b * b for b in v2))
    if norm1 < 1e-9 or norm2 < 1e-9:
        return 0.0
    return dot / (norm1 * norm2)
