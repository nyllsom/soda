def prediction_error(targets, predictions):
    residual = targets - predictions
    squared = residual ** 2
    loss = squared.mean()
    return loss
