import random

import numpy as np

from caso_uso_llm.seed import set_seed


def test_misma_semilla_mismos_numeros():
    set_seed(123)
    a = (random.random(), np.random.rand(3).tolist())
    set_seed(123)
    b = (random.random(), np.random.rand(3).tolist())
    assert a == b
