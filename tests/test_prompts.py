from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))

from prompts import (
    load_final_system_instruction,
    load_list_mode_addenda,
    load_prompt_file,
    load_system_instruction,
)


class PromptTests(unittest.TestCase):
    def test_loads_all_prompt_blocks_in_order(self):
        with patch(
            "prompts.Path.read_text",
            side_effect=[
                "Role",
                "Rules",
                "Security",
                "Tools",
                "Operator",
                "Knowledge",
            ],
        ):
            instruction = load_system_instruction()

        self.assertEqual(
            instruction,
            "Role\n\nRules\n\nSecurity\n\nTools\n\nOperator\n\nKnowledge",
        )

    def test_loads_the_final_system_instruction_without_search_rules(self):
        with patch(
            "prompts.Path.read_text",
            side_effect=["Role", "Rules", "Security", "Operator", "Knowledge"],
        ):
            instruction = load_final_system_instruction()

        self.assertEqual(
            instruction,
            "Role\n\nRules\n\nSecurity\n\nOperator\n\nKnowledge",
        )

    def test_loads_one_special_prompt(self):
        with patch("prompts.Path.read_text", return_value=" Selection rules "):
            instruction = load_prompt_file("prompts/product_selection.md")

        self.assertEqual(instruction, "Selection rules")

    def test_loads_the_list_mode_addenda(self):
        with patch(
            "prompts.Path.read_text",
            side_effect=[
                "Decision addendum",
                "Selection addendum",
                "Item addendum",
                "Report addendum",
            ],
        ):
            addenda = load_list_mode_addenda()

        self.assertEqual(
            addenda,
            {
                "decision": "Decision addendum",
                "selection": "Selection addendum",
                "item_response": "Item addendum",
                "report": "Report addendum",
            },
        )

    def test_reports_a_missing_prompt_file(self):
        with patch("prompts.Path.read_text", side_effect=FileNotFoundError):
            with self.assertRaisesRegex(RuntimeError, "Could not read prompt file"):
                load_system_instruction()

    def test_reports_an_empty_prompt_file(self):
        with patch(
            "prompts.Path.read_text",
            side_effect=["Role", "Rules", "", "Tools", "Operator", "Knowledge"],
        ):
            with self.assertRaisesRegex(RuntimeError, "Prompt file is empty"):
                load_system_instruction()
