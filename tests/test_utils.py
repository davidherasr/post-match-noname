from core.utils import normalize_name


def test_normalize_name_unicode():
    assert normalize_name("  Pau Cubarsí ") == "pau cubarsi"
    assert normalize_name("Wojciech  Szczęsny") == "wojciech szczesny"
    assert normalize_name("محمد صلاح")
    assert normalize_name("Михаил Иванов")
