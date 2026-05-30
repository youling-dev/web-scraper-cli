"""
JSON Schema validation for wscraper output.

Allows users to define an expected output structure and validate
scraped results against it. Catches website structure changes
before bad data propagates downstream.

Usage:
    from .schema import SchemaValidator

    schema = {
        "type": "array",
        "items": {
            "type": "object",
            "required": ["title", "price"],
            "properties": {
                "title": {"type": "string", "minLength": 1},
                "price": {"type": "number", "minimum": 0},
                "url": {"type": "string", "format": "uri"},
            }
        }
    }

    validator = SchemaValidator(schema)
    valid, errors = validator.validate(data)

CLI:
    wscraper https://example.com --select ".product" --schema schema.json
    wscraper https://example.com --select ".product" --schema '{"type":"array","items":{"type":"object","required":["title"]}}'

Schema file format (JSON):
    Standard JSON Schema (Draft 7 subset).
    Supports: type, required, properties, minLength, maxLength, minimum, maximum,
              pattern, enum, format (uri/email/date-time), items (for arrays).

Also supports a simplified shorthand:
    {"required": ["field1", "field2"], "types": {"field1": "string", "field2": "number"}}
"""

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


class SchemaValidator:
    """Lightweight JSON Schema validator (Draft 7 subset, no external deps)."""

    # Supported format patterns
    FORMAT_PATTERNS = {
        "uri": r"^https?://\S+",
        "email": r"^\S+@\S+\.\S+$",
        "date-time": r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}",
        "date": r"^\d{4}-\d{2}-\d{2}$",
        "time": r"^\d{2}:\d{2}:\d{2}",
        "ipv4": r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$",
    }

    def __init__(self, schema: Dict[str, Any], strict: bool = False):
        """
        Args:
            schema: JSON Schema dict (or simplified shorthand)
            strict: If True, reject items with extra keys not in schema.properties
        """
        self.raw_schema = schema
        self.schema = self._normalize(schema)
        self.strict = strict

    @classmethod
    def from_file(cls, path: str, strict: bool = False) -> "SchemaValidator":
        """Load schema from a JSON file."""
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"Schema file not found: {path}")
        schema = json.loads(p.read_text(encoding="utf-8"))
        return cls(schema, strict=strict)

    @classmethod
    def from_string(cls, text: str, strict: bool = False) -> "SchemaValidator":
        """Load schema from a JSON string."""
        schema = json.loads(text)
        return cls(schema, strict=strict)

    def _normalize(self, schema: Dict[str, Any]) -> Dict[str, Any]:
        """Convert simplified shorthand to standard JSON Schema format.

        Shorthand: {"required": ["a", "b"], "types": {"a": "string"}}
        Standard:  {"type": "object", "required": ["a", "b"], "properties": {"a": {"type": "string"}}}
        """
        if "types" in schema:
            # Simplified shorthand
            types = schema.pop("types")
            properties = {}
            for field, ftype in types.items():
                prop = {"type": ftype}
                # Merge any field-level constraints
                if isinstance(ftype, dict):
                    prop = ftype
                properties[field] = prop
            schema = {
                "type": "object",
                "required": schema.get("required", []),
                "properties": properties,
            }
        return schema

    def validate(self, data: Any) -> Tuple[bool, List[str]]:
        """
        Validate data against schema.

        Returns:
            (is_valid, list_of_error_messages)
        """
        errors: List[str] = []
        self._validate_node(data, self.schema, "", errors)
        return len(errors) == 0, errors

    def _validate_node(self, data: Any, schema: Dict[str, Any], path: str, errors: List[str]) -> None:
        """Recursively validate a data node against a schema node."""
        if not schema:
            return

        node_path = path or "(root)"

        # Type check
        expected_type = schema.get("type")
        if expected_type and not self._check_type(data, expected_type):
            actual = self._python_type_name(data)
            errors.append(f"{node_path}: expected type '{expected_type}', got '{actual}'")
            return  # No point checking further if type is wrong

        # Enum
        if "enum" in schema:
            if data not in schema["enum"]:
                errors.append(f"{node_path}: value {data!r} not in allowed values {schema['enum']}")

        # String constraints
        if isinstance(data, str):
            if "minLength" in schema and len(data) < schema["minLength"]:
                errors.append(f"{node_path}: string length {len(data)} < minLength {schema['minLength']}")
            if "maxLength" in schema and len(data) > schema["maxLength"]:
                errors.append(f"{node_path}: string length {len(data)} > maxLength {schema['maxLength']}")
            if "pattern" in schema and not re.search(schema["pattern"], data):
                errors.append(f"{node_path}: string does not match pattern '{schema['pattern']}'")
            if "format" in schema:
                fmt = schema["format"]
                if fmt in self.FORMAT_PATTERNS:
                    if not re.match(self.FORMAT_PATTERNS[fmt], data):
                        errors.append(f"{node_path}: string does not match format '{fmt}'")

        # Numeric constraints
        if isinstance(data, (int, float)) and not isinstance(data, bool):
            if "minimum" in schema and data < schema["minimum"]:
                errors.append(f"{node_path}: value {data} < minimum {schema['minimum']}")
            if "maximum" in schema and data > schema["maximum"]:
                errors.append(f"{node_path}: value {data} > maximum {schema['maximum']}")
            if "exclusiveMinimum" in schema and data <= schema["exclusiveMinimum"]:
                errors.append(f"{node_path}: value {data} <= exclusiveMinimum {schema['exclusiveMinimum']}")
            if "exclusiveMaximum" in schema and data >= schema["exclusiveMaximum"]:
                errors.append(f"{node_path}: value {data} >= exclusiveMaximum {schema['exclusiveMaximum']}")

        # Object validation
        if isinstance(data, dict):
            # Required fields
            for req in schema.get("required", []):
                if req not in data:
                    errors.append(f"{node_path}: missing required field '{req}'")

            # Property-level validation
            properties = schema.get("properties", {})
            for key, prop_schema in properties.items():
                if key in data:
                    self._validate_node(data[key], prop_schema, f"{node_path}.{key}", errors)

            # Strict mode: reject extra keys
            if self.strict and properties:
                for key in data:
                    if key not in properties:
                        errors.append(f"{node_path}: unexpected field '{key}' (strict mode)")

        # Array validation
        if isinstance(data, list):
            if "minItems" in schema and len(data) < schema["minItems"]:
                errors.append(f"{node_path}: array length {len(data)} < minItems {schema['minItems']}")
            if "maxItems" in schema and len(data) > schema["maxItems"]:
                errors.append(f"{node_path}: array length {len(data)} > maxItems {schema['maxItems']}")
            if "items" in schema:
                for i, item in enumerate(data):
                    self._validate_node(item, schema["items"], f"{node_path}[{i}]", errors)

    def _check_type(self, data: Any, type_name: str) -> bool:
        """Check if data matches JSON Schema type name."""
        type_map = {
            "string": lambda d: isinstance(d, str),
            "number": lambda d: isinstance(d, (int, float)) and not isinstance(d, bool),
            "integer": lambda d: isinstance(d, int) and not isinstance(d, bool),
            "boolean": lambda d: isinstance(d, bool),
            "array": lambda d: isinstance(d, list),
            "object": lambda d: isinstance(d, dict),
            "null": lambda d: d is None,
        }
        checker = type_map.get(type_name)
        if checker:
            return checker(data)
        return True  # Unknown type = pass

    @staticmethod
    def _python_type_name(data: Any) -> str:
        """Map Python type to JSON Schema type name."""
        if data is None:
            return "null"
        if isinstance(data, bool):
            return "boolean"
        if isinstance(data, int):
            return "integer"
        if isinstance(data, float):
            return "number"
        if isinstance(data, str):
            return "string"
        if isinstance(data, list):
            return "array"
        if isinstance(data, dict):
            return "object"
        return type(data).__name__

    def validate_and_filter(self, data: List[Any], mode: str = "warn") -> Tuple[List[Any], List[Dict[str, Any]]]:
        """Validate each item in a list, optionally filtering invalid ones.

        Args:
            data: List of items to validate (typically scraped results)
            mode: 'warn' (keep all, print warnings), 'filter' (remove invalid),
                  'strict' (raise on first error)

        Returns:
            (filtered_data, list_of_validation_results)
        """
        # Wrap data in array schema if our schema is for objects
        items_schema = self.schema.get("items", self.schema)
        valid_data = []
        results = []

        for i, item in enumerate(data):
            is_valid, errors = self._validate_node_result(item, items_schema, i)

            if is_valid:
                valid_data.append(item)
                results.append({"index": i, "valid": True})
            else:
                results.append({"index": i, "valid": False, "errors": errors})

                if mode == "strict":
                    raise ValueError(
                        f"Schema validation failed at index {i}: {'; '.join(errors)}"
                    )
                elif mode == "warn":
                    error_str = "; ".join(errors)
                    print(f"  ⚠️  Schema warning [item {i}]: {error_str}", file=__import__("sys").stderr)
                    valid_data.append(item)  # Keep it in warn mode

        return valid_data, results

    def _validate_node_result(self, data: Any, schema: Dict, index: int) -> Tuple[bool, List[str]]:
        """Validate single item, returning (valid, errors)."""
        errors: List[str] = []
        self._validate_node(data, schema, f"[{index}]", errors)
        return len(errors) == 0, errors
