from caso_uso_llm.raw_integrity import verify


def test_data_raw_no_ha_cambiado():
    assert verify() == []
