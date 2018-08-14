from src.utils import ensure
import pytest

def test_ensure():
    ensure(1 == 1, "working")
    with pytest.raises(AssertionError):
        ensure(1 == 2, "not working")    

