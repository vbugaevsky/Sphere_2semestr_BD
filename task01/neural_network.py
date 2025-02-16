# -*- coding: utf-8 -*-

import numpy as np
import random
from abc import ABCMeta, abstractmethod
import warnings


class NeuralLayer:
    __metaclass__ = ABCMeta

    def __init__(self, n_neurons, bias=True):
        self.n_neurons = n_neurons
        self.n_objects = None
        self.bias_use = bias

    @abstractmethod
    def forward(self, values_in, weights):
        pass

    @abstractmethod
    def backward(self, errors_in, weights):
        pass


class SequentialLayer(NeuralLayer):
    __metaclass__ = ABCMeta

    @abstractmethod
    def _activation(self, values_in):
        pass

    def forward(self, values_in, weights):
        self.values_in = np.asarray(np.asmatrix(values_in) * weights)
        self.values_out = self._activation(self.values_in)
        self.bias = np.ones(self.n_objects) if self.bias_use else np.zeros(self.n_objects)

    @abstractmethod
    def _activation_derivative(self, values_in, values_out):
        pass

    def backward(self, errors_in, weights):
        derivative = self._activation_derivative(self.values_in, self.values_out)
        if errors_in is None:
            self.deltas = derivative * np.asarray(weights)
            self.deltas = np.asarray(np.c_[self.deltas, np.zeros(self.deltas.shape[0])])
            self.derivatives = None
        else:
            self.deltas = np.c_[derivative, self.bias] * np.asarray(np.asmatrix(errors_in) * np.asmatrix(weights).T)
            values = np.c_[self.values_out, self.bias]
            self.derivatives = np.asarray([
                np.asarray(np.asmatrix(values[i]).T * np.asmatrix(errors_in[i]))
                for i in range(self.n_objects)
            ])


class SigmoidLayer(SequentialLayer):
    def _activation(self, values_in):
        return 1.0 / (1.0 + np.exp(-values_in))

    def _activation_derivative(self, values_in, values_out):
        return values_out * (1.0 - values_out)


class IdentityLayer(SequentialLayer):
    def _activation(self, values_in):
        return values_in

    def _activation_derivative(self, values_in, values_out):
        return np.ones(values_out.shape)


class SoftmaxLayer(NeuralLayer):
    def _activation(self, values_in):
        res = np.exp(values_in)
        return res / np.sum(res, axis=1).reshape(res.shape[0], 1)

    def forward(self, values_in, weights):
        self.values_in = np.asarray(np.asmatrix(values_in) * weights)
        self.values_out = self._activation(self.values_in)

    def backward(self, errors_in, weights):
        if errors_in is None:
            self.deltas = self.values_out - weights
            self.deltas = np.asarray(np.c_[self.deltas, np.zeros(self.deltas.shape[0])])
            self.derivatives = None
        else:
            raise


class ReluLayer(SequentialLayer):
    def _activation(self, values_in):
        return np.maximum(values_in, 0)

    def _activation_derivative(self, values_in, values_out):
        return (values_out > 0).astype(int)


class SoftplusLayer(SequentialLayer):
    def _activation(self, values_in):
        return np.log(1.0 + np.exp(values_in))

    def _activation_derivative(self, values_in, values_out):
        return 1.0 / (1.0 + np.exp(-values_in))


class InputLayer(SequentialLayer):
    def __init__(self, X, bias):
        SequentialLayer.__init__(self, X.shape[1], bias)
        self.values_in = None
        self.values_out = X
        self.n_objects = X.shape[0]
        self.bias = np.ones(self.n_objects) if bias else np.zeros(self.n_objects)

    def _activation(self, values_in):
        return values_in

    def _activation_derivative(self, values_in, values_out):
        return np.ones(values_out.shape)

class NeuralNetwork:
    def __init__(self, layers, input_bias=True,
                 loss_function='MSE',
                 regular_type='l2', alpha=1e-4):
        self.layers = [None] + layers
        self.loss_function = loss_function
        self.regular_type = regular_type
        self.alpha = alpha
        self.input_bias = input_bias

        self.weights = None

    def __criteria(self, predicted, observed):
        loss = {
            'MSE': lambda y, t: .5 * np.mean(np.sum(np.square(y - t), axis=1)),
            'NLL': lambda y, t: np.mean(-np.sum(t * np.log(y), axis=1)),
        }

        regular = {
            None: lambda w: 0,
            'l1': lambda w: np.sum(np.abs(w)),
            'l2': lambda w: .5 * np.sum(np.square(w))
        }

        return loss[self.loss_function](predicted, observed) + \
               self.alpha * np.sum([regular[self.regular_type](w) for w in self.weights])

    def __loss_derivative(self, predicted, observed):
        loss = {
            'MSE': lambda y, t: y - t,
            'NLL': lambda y, t: - t / y
        }
        return loss[self.loss_function](predicted, observed)

    def __regular_derivative(self, weight):
        regular = {
            None: lambda w: np.zeros(w.shape),
            'l1': lambda w: np.sign(w.copy()),
            'l2': lambda w: w.copy()
        }
        return regular[self.regular_type](weight)

    def __forward_step(self):
        for idx, w in enumerate(self.weights):
            values_in = np.c_[self.layers[idx].values_out, self.layers[idx].bias]
            self.layers[idx + 1].forward(values_in, w)
        return self.layers[-1].values_out

    def __backward_step(self):
        n_layers = len(self.layers)
        for idx in range(n_layers - 1, -1, -1):
            if idx == n_layers - 1:
                if self.softmax:
                    args = (None, self.y)
                else:
                    args = (None, self.__loss_derivative(self.layers[idx].values_out, self.y))
            else:
                args = (self.layers[idx + 1].deltas[:, :-1], self.weights[idx])
            self.layers[idx].backward(*args)

    def __update_weights(self):
        for idx, layer in enumerate(self.layers[:-1]):
            self.weights[idx] -= self.learning_rate * (
                np.mean(layer.derivatives, axis=0) +
                self.alpha * self.__regular_derivative(self.weights[idx])
            )

    def set_random_weights(self, X):
        self.weights = []
        for idx in range(len(self.layers) - 1):
            M = (self.layers[idx].n_neurons if idx else X.shape[1]) + 1
            N = self.layers[idx + 1].n_neurons
            self.weights.append(np.random.rand(M, N) - .5)

    def __epoch(self, X, Y, batch_size):
        if batch_size is None:
            batches = [range(X.shape[0])]
        else:
            rand_sample = random.sample(range(X.shape[0]), X.shape[0])
            batches = [rand_sample[i:i + batch_size] for i in range(0, len(rand_sample), batch_size)]

        for batch in batches:
            self.train_on_batch(X, Y, batch)

    def __batch_init(self, X, Y, batch):
        n_objects = len(batch)
        self.layers[0] = InputLayer(X[batch].reshape(n_objects, X.shape[1]), self.input_bias)
        self.y = Y[batch].reshape(n_objects, Y.shape[1]) if Y is not None else None

        for layer in self.layers:
            layer.n_objects = n_objects

    def train_on_batch(self, X, Y, batch):
        self.__batch_init(X, Y, batch)
        self.__forward_step()
        self.__backward_step()
        # self.__gradient_check()
        self.__update_weights()

    def fit(self, X, Y, n_epoch=5, batch_size=25, learning_params=(0.5, 0.75, 65), test_size=0):
        if self.weights is not None:
            warnings.warn("You mast have forgotten to prepare weights!\n See the function: set_random_weights(X)\n")
        print '',

        self.softmax = self.layers[-1].__class__.__name__ == 'SoftmaxLayer'
        if (self.weights is None) or (len(self.weights) != len(self.layers) - 1):
            self.set_random_weights(X)

        self.error_train, self.error_test = [], []
        self.learning_rate = learning_params[0]

        sample = random.sample(range(X.shape[0]), X.shape[0])
        X, Y = X[sample], Y[sample]
        border = X.shape[0] * test_size
        X_test, X_train = X[:border], X[border:]
        Y_test, Y_train = Y[:border], Y[border:]

        for epoch in range(n_epoch):
            if (epoch + 1) % learning_params[2] == 0:
                self.learning_rate *= learning_params[1]

            self.__epoch(X_train, Y_train, batch_size)

            criteria_train = self.__criteria(self.predict(X_train, batch_size=batch_size), Y_train)
            self.error_train.append(criteria_train)

            print '\r', 'epoch = {}'.format(epoch), 'error = {}'.format(criteria_train), \
                'learning_rate = {}'.format(self.learning_rate),

            if test_size != 0.0:
                criteria_test = self.__criteria(self.predict(X_test, batch_size=batch_size), Y_test)
                self.error_test.append(criteria_test)

        print ''

    def predict(self, X, batch_size=25):
        sample = range(X.shape[0])
        if batch_size is None:
            batches = [sample]
        else:
            batches = [sample[i:i + batch_size] for i in range(0, X.shape[0], batch_size)]
        predicted = None
        for batch in batches:
            self.__batch_init(X, None, batch)
            predicted_batch = self.__forward_step()
            predicted = predicted_batch if predicted is None else np.r_[predicted, predicted_batch]
        return predicted

    def __gradient_check(self):
        eps = 1e-3

        gradient_residual, gradient_analytic = [], []

        for idx, layer in enumerate(self.layers[:-1]):
            for i in range(self.weights[idx].shape[0]):
                for j in range(self.weights[idx].shape[1]):
                    self.weights[idx][i, j] -= eps
                    J_before = self.__criteria(predicted=self.__forward_step(), observed=self.y)

                    self.weights[idx][i, j] += 2.0 * eps
                    J_after = self.__criteria(predicted=self.__forward_step(), observed=self.y)

                    self.weights[idx][i, j] -= eps

                    deriv_residual = (J_after - J_before) / (2.0 * eps)
                    deriv_analytic = np.mean(layer.derivatives, axis=0) + \
                                     self.alpha * self.__regular_derivative(self.weights[idx])
                    deriv_analytic = deriv_analytic[i, j]

                    gradient_residual.append(deriv_residual)
                    gradient_analytic.append(deriv_analytic)

                    if not np.isclose(deriv_residual, deriv_analytic, atol=eps):
                        message = 'Matrix {}. Cell {}\n'.format(idx, (i, j)) +\
                                  'Residual derivative = {}\n'.format(deriv_residual) + \
                                  'Analytic derivative = {}\n'.format(deriv_analytic) + \
                                  str(abs(deriv_residual - deriv_analytic)) + '\n'
                        raise Exception('Wrong derivative!\n' + message)
                        # print 'raised'

        def norm(x):
            return np.sum(np.square(gradient_analytic))

        gradient_analytic = np.asarray(gradient_analytic)
        gradient_residual = np.asarray(gradient_residual)

        # print '\nGradient analytic (norm^2): ', norm(gradient_analytic)
        # print 'Gradient residual (norm^2): ', norm(gradient_residual)
        # print norm(gradient_analytic - gradient_residual) / norm(gradient_analytic + gradient_residual)
        # print '-'*40

        self.__forward_step()


if __name__ == '__main__':
    multip = 10
    dfX = np.array([[.05, .10]] * multip)
    dfY = np.array([[.01, .99]] * multip)

    nn = NeuralNetwork(layers=[
        SigmoidLayer(2, bias=True),
        SigmoidLayer(2, bias=False),
    ], input_bias=True, loss_function='MSE', regular_type='l2', alpha=10)

    nn.fit(dfX, dfY, n_epoch=10, batch_size=None, learning_params=(0.1, 0.75, 65))
    r = nn.predict(dfX, batch_size=10)