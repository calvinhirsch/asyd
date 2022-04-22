expected_results = {
    "": {
        "exception": None,
        "result": {
            "some_field": "???",
            "nested_config": {
                "some_nested_field": "???"
            }
        }
    },
    "--some_field=ello --nested_config.some_nested_field=101": {
        "exception": None,
        "result": {
            "some_field": "ello",
            "nested_config": {
                "some_nested_field": 101
            }
        }
    }
}
