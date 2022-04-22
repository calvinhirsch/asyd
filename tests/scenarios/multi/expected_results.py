expected_results = {
    "--some_multi=first": {
        "exception": None,
        "result": {
            "some_field": "???",
            "some_multi": {
                "_selected": "first",
                "field_a": "???"
            }
        }
    },
    "--some_field=yes --some_multi=first": {
        "exception": None,
        "result": {
            "some_field": "yes",
            "some_multi":  {
                "_selected": "first",
                "field_a": "???"
            }
        }
    },
    "--some_multi=second": {
        "exception": None,
        "result": {
            "some_field": "???",
            "some_multi": {
                "_selected": "second",
                "field_a": "???"
            }
        }
    },
    "--some_multi=third": {
        "exception": None,
        "result": {
            "some_field": "???",
            "some_multi": {
                "_selected": "third",
                "field_b": "???"
            }
        }
    },
}
