expected_results = {
    "": {
        "exception": None,
        "result": {
            "some_field": "oy",
            "nested_config": {
                "some_nested_field": 99
            }
        }
    },
    "--some_field=guh --nested_config.some_nested_field=9999": {
        "exception": None,
        "result": {
            "some_field": "guh",
            "nested_config": {
                "some_nested_field": 9999
            }
        }
    }
}
