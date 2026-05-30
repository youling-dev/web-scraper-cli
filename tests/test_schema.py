"""Tests for wscraper.schema — SchemaValidator."""
import json
import pytest
import tempfile
import os
from wscraper.schema import SchemaValidator


class TestSchemaValidatorBasic:
    """Basic type validation."""

    def test_string_type_valid(self):
        schema = {"type": "string"}
        v = SchemaValidator(schema)
        assert v.validate("hello") == (True, [])

    def test_string_type_invalid(self):
        schema = {"type": "string"}
        v = SchemaValidator(schema)
        assert v.validate(123) == (False, ["(root): expected type 'string', got 'integer'"])

    def test_number_type_valid(self):
        schema = {"type": "number"}
        v = SchemaValidator(schema)
        assert v.validate(42) == (True, [])
        assert v.validate(3.14) == (True, [])

    def test_number_type_rejects_bool(self):
        schema = {"type": "number"}
        v = SchemaValidator(schema)
        assert v.validate(True)[0] is False

    def test_integer_type(self):
        schema = {"type": "integer"}
        v = SchemaValidator(schema)
        assert v.validate(42) == (True, [])
        assert v.validate(3.14)[0] is False

    def test_boolean_type(self):
        schema = {"type": "boolean"}
        v = SchemaValidator(schema)
        assert v.validate(True) == (True, [])
        assert v.validate(False) == (True, [])
        assert v.validate(1)[0] is False

    def test_array_type(self):
        schema = {"type": "array"}
        v = SchemaValidator(schema)
        assert v.validate([1, 2, 3]) == (True, [])
        assert v.validate("not array")[0] is False

    def test_object_type(self):
        schema = {"type": "object"}
        v = SchemaValidator(schema)
        assert v.validate({"a": 1}) == (True, [])
        assert v.validate([1, 2])[0] is False

    def test_null_type(self):
        schema = {"type": "null"}
        v = SchemaValidator(schema)
        assert v.validate(None) == (True, [])
        assert v.validate("")[0] is False


class TestSchemaStringConstraints:
    def test_min_length(self):
        schema = {"type": "string", "minLength": 3}
        v = SchemaValidator(schema)
        assert v.validate("hi")[0] is False
        assert v.validate("abc") == (True, [])
        assert v.validate("abcd") == (True, [])

    def test_max_length(self):
        schema = {"type": "string", "maxLength": 5}
        v = SchemaValidator(schema)
        assert v.validate("abcdef")[0] is False
        assert v.validate("abc") == (True, [])

    def test_pattern(self):
        schema = {"type": "string", "pattern": r"^\d{3}-\d{4}$"}
        v = SchemaValidator(schema)
        assert v.validate("123-4567") == (True, [])
        assert v.validate("12-4567")[0] is False

    def test_format_uri(self):
        schema = {"type": "string", "format": "uri"}
        v = SchemaValidator(schema)
        assert v.validate("https://example.com") == (True, [])
        assert v.validate("not-a-uri")[0] is False

    def test_format_email(self):
        schema = {"type": "string", "format": "email"}
        v = SchemaValidator(schema)
        assert v.validate("test@example.com") == (True, [])
        assert v.validate("invalid")[0] is False


class TestSchemaNumericConstraints:
    def test_minimum(self):
        schema = {"type": "number", "minimum": 0}
        v = SchemaValidator(schema)
        assert v.validate(-1)[0] is False
        assert v.validate(0) == (True, [])
        assert v.validate(100) == (True, [])

    def test_maximum(self):
        schema = {"type": "number", "maximum": 100}
        v = SchemaValidator(schema)
        assert v.validate(101)[0] is False
        assert v.validate(100) == (True, [])

    def test_exclusive_minimum(self):
        schema = {"type": "number", "exclusiveMinimum": 0}
        v = SchemaValidator(schema)
        assert v.validate(0)[0] is False
        assert v.validate(0.01) == (True, [])

    def test_exclusive_maximum(self):
        schema = {"type": "number", "exclusiveMaximum": 100}
        v = SchemaValidator(schema)
        assert v.validate(100)[0] is False
        assert v.validate(99.99) == (True, [])


class TestSchemaObject:
    def test_required_fields(self):
        schema = {
            "type": "object",
            "required": ["name", "age"],
            "properties": {
                "name": {"type": "string"},
                "age": {"type": "integer"},
            },
        }
        v = SchemaValidator(schema)
        assert v.validate({"name": "Alice", "age": 30}) == (True, [])
        valid, errors = v.validate({"name": "Alice"})
        assert valid is False
        assert any("missing required field 'age'" in e for e in errors)

    def test_nested_properties(self):
        schema = {
            "type": "object",
            "properties": {
                "address": {
                    "type": "object",
                    "required": ["city"],
                    "properties": {
                        "city": {"type": "string"},
                        "zip": {"type": "string", "pattern": r"^\d{5}$"},
                    },
                }
            },
        }
        v = SchemaValidator(schema)
        assert v.validate({"address": {"city": "Beijing"}}) == (True, [])
        valid, _ = v.validate({"address": {"zip": "12345"}})
        assert valid is False

    def test_strict_mode_rejects_extra_keys(self):
        schema = {
            "type": "object",
            "properties": {"name": {"type": "string"}},
        }
        v = SchemaValidator(schema, strict=True)
        valid, errors = v.validate({"name": "Alice", "extra": True})
        assert valid is False
        assert any("unexpected field 'extra'" in e for e in errors)

    def test_strict_mode_allows_defined_keys(self):
        schema = {
            "type": "object",
            "properties": {"name": {"type": "string"}},
        }
        v = SchemaValidator(schema, strict=True)
        assert v.validate({"name": "Alice"}) == (True, [])


class TestSchemaArray:
    def test_items_validation(self):
        schema = {
            "type": "array",
            "items": {"type": "number", "minimum": 0},
        }
        v = SchemaValidator(schema)
        assert v.validate([1, 2, 3]) == (True, [])
        valid, _ = v.validate([1, -2, 3])
        assert valid is False

    def test_min_items(self):
        schema = {"type": "array", "minItems": 2}
        v = SchemaValidator(schema)
        assert v.validate([1])[0] is False
        assert v.validate([1, 2]) == (True, [])

    def test_max_items(self):
        schema = {"type": "array", "maxItems": 2}
        v = SchemaValidator(schema)
        assert v.validate([1, 2, 3])[0] is False
        assert v.validate([1, 2]) == (True, [])


class TestSchemaEnum:
    def test_enum_valid(self):
        schema = {"type": "string", "enum": ["red", "green", "blue"]}
        v = SchemaValidator(schema)
        assert v.validate("red") == (True, [])
        assert v.validate("yellow")[0] is False


class TestSchemaShorthand:
    def test_normalize_shorthand(self):
        schema = {"required": ["title", "price"], "types": {"title": "string", "price": "number"}}
        v = SchemaValidator(schema)
        # Should convert to standard format
        assert v.schema["type"] == "object"
        assert "properties" in v.schema
        assert v.schema["required"] == ["title", "price"]

    def test_shorthand_validation(self):
        schema = {"required": ["name"], "types": {"name": "string"}}
        v = SchemaValidator(schema)
        assert v.validate({"name": "test"}) == (True, [])
        assert v.validate({"other": "test"})[0] is False


class TestSchemaFileLoading:
    def test_from_file(self):
        schema = {"type": "object", "required": ["id"], "properties": {"id": {"type": "integer"}}}
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(schema, f)
            f.flush()
            v = SchemaValidator.from_file(f.name)
            assert v.validate({"id": 42}) == (True, [])
            os.unlink(f.name)

    def test_from_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            SchemaValidator.from_file("/nonexistent/schema.json")

    def test_from_string(self):
        v = SchemaValidator.from_string('{"type":"string","minLength":1}')
        assert v.validate("hello") == (True, [])
        assert v.validate("")[0] is False


class TestSchemaValidateAndFilter:
    def test_warn_mode_keeps_all(self, capsys):
        schema = {
            "type": "array",
            "items": {"type": "object", "required": ["name"], "properties": {"name": {"type": "string"}}},
        }
        v = SchemaValidator(schema)
        data = [{"name": "ok"}, {"other": "no name"}]
        valid_data, results = v.validate_and_filter(data, mode="warn")
        assert len(valid_data) == 2  # warn keeps all
        assert results[1]["valid"] is False

    def test_filter_mode_removes_invalid(self):
        schema = {
            "type": "array",
            "items": {"type": "object", "required": ["name"], "properties": {"name": {"type": "string"}}},
        }
        v = SchemaValidator(schema)
        data = [{"name": "ok"}, {"other": "no name"}]
        valid_data, results = v.validate_and_filter(data, mode="filter")
        assert len(valid_data) == 1
        assert valid_data[0]["name"] == "ok"

    def test_strict_mode_raises(self):
        schema = {
            "type": "array",
            "items": {"type": "object", "required": ["name"], "properties": {"name": {"type": "string"}}},
        }
        v = SchemaValidator(schema)
        data = [{"name": "ok"}, {"other": "no name"}]
        with pytest.raises(ValueError, match="Schema validation failed at index 1"):
            v.validate_and_filter(data, mode="strict")
