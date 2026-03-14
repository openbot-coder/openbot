#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Unit tests for tool_messages_utils module."""

import json
import logging
from unittest.mock import MagicMock
import pytest
from openbot.utils.tool_messages_utils import (
    extract_tool_ids,
    check_valid_messages,
    _reorder_tool_results,
    _remove_unpaired_tool_messages,
    _dedup_tool_blocks,
    _remove_invalid_tool_blocks,
    _repair_empty_tool_inputs,
    _sanitize_tool_messages,
    _truncate_text,
)


class MockMsg:
    """Mock Msg class for testing."""
    def __init__(self, content):
        self.content = content


class TestExtractToolIds:
    """Test extract_tool_ids function."""
    
    def test_normal_tool_use(self):
        """Test normal input with tool_use block."""
        msg = MockMsg([
            {"type": "tool_use", "id": "tool_123", "name": "test_tool", "input": {}}
        ])
        uses, results = extract_tool_ids(msg)
        assert uses == {"tool_123"}
        assert results == set()
    
    def test_normal_tool_result(self):
        """Test normal input with tool_result block."""
        msg = MockMsg([
            {"type": "tool_result", "id": "tool_123", "content": "result"}
        ])
        uses, results = extract_tool_ids(msg)
        assert uses == set()
        assert results == {"tool_123"}
    
    def test_mixed_blocks(self):
        """Test message with both tool_use and tool_result blocks."""
        msg = MockMsg([
            {"type": "tool_use", "id": "tool_1", "name": "tool1", "input": {}},
            {"type": "tool_result", "id": "tool_2", "content": "result"},
            {"type": "text", "content": "hello"},
            {"type": "tool_use", "id": "tool_3", "name": "tool3", "input": {}}
        ])
        uses, results = extract_tool_ids(msg)
        assert uses == {"tool_1", "tool_3"}
        assert results == {"tool_2"}
    
    def test_empty_content(self):
        """Test message with empty content list."""
        msg = MockMsg([])
        uses, results = extract_tool_ids(msg)
        assert uses == set()
        assert results == set()
    
    def test_non_list_content(self):
        """Test message with non-list content (string)."""
        msg = MockMsg("plain text message")
        uses, results = extract_tool_ids(msg)
        assert uses == set()
        assert results == set()
    
    def test_no_id_blocks(self):
        """Test tool blocks without id field."""
        msg = MockMsg([
            {"type": "tool_use", "name": "test_tool", "input": {}},  # missing id
            {"type": "tool_result", "content": "result"}  # missing id
        ])
        uses, results = extract_tool_ids(msg)
        assert uses == set()
        assert results == set()
    
    def test_unknown_block_types(self):
        """Test with unknown block types."""
        msg = MockMsg([
            {"type": "text", "content": "hello"},
            {"type": "image", "url": "test.png"},
            {"type": "tool_use", "id": "tool_1", "name": "test", "input": {}}
        ])
        uses, results = extract_tool_ids(msg)
        assert uses == {"tool_1"}
        assert results == set()


class TestCheckValidMessages:
    """Test check_valid_messages function."""
    
    def test_valid_paired_messages(self):
        """Test valid messages with all tool_use paired with tool_result."""
        messages = [
            MockMsg([{"type": "tool_use", "id": "tool_1", "name": "t1", "input": {}}]),
            MockMsg([{"type": "tool_result", "id": "tool_1", "content": "res1"}]),
            MockMsg([{"type": "tool_use", "id": "tool_2", "name": "t2", "input": {}}]),
            MockMsg([{"type": "tool_result", "id": "tool_2", "content": "res2"}])
        ]
        assert check_valid_messages(messages) is True
    
    def test_unpaired_tool_use(self):
        """Test messages with unpaired tool_use."""
        messages = [
            MockMsg([{"type": "tool_use", "id": "tool_1", "name": "t1", "input": {}}]),
            MockMsg([{"type": "tool_result", "id": "tool_1", "content": "res1"}]),
            MockMsg([{"type": "tool_use", "id": "tool_2", "name": "t2", "input": {}}])
            # Missing tool_result for tool_2
        ]
        assert check_valid_messages(messages) is False
    
    def test_unpaired_tool_result(self):
        """Test messages with unpaired tool_result."""
        messages = [
            MockMsg([{"type": "tool_use", "id": "tool_1", "name": "t1", "input": {}}]),
            MockMsg([{"type": "tool_result", "id": "tool_1", "content": "res1"}]),
            MockMsg([{"type": "tool_result", "id": "tool_2", "content": "res2"}])
            # Missing tool_use for tool_2
        ]
        assert check_valid_messages(messages) is False
    
    def test_empty_messages_list(self):
        """Test empty messages list."""
        assert check_valid_messages([]) is True
    
    def test_no_tool_messages(self):
        """Test messages without any tool blocks."""
        messages = [
            MockMsg("plain text"),
            MockMsg([{"type": "text", "content": "hello"}])
        ]
        assert check_valid_messages(messages) is True
    
    def test_multiple_uses_one_result(self):
        """Test multiple tool_use with same id but only one result."""
        messages = [
            MockMsg([{"type": "tool_use", "id": "tool_1", "name": "t1", "input": {}}]),
            MockMsg([{"type": "tool_use", "id": "tool_1", "name": "t1", "input": {}}]),
            MockMsg([{"type": "tool_result", "id": "tool_1", "content": "res1"}])
        ]
        # check_valid_messages only checks set equality, not count
        # So 2 uses and 1 result with same id will return True (sets are equal)
        assert check_valid_messages(messages) is True


class TestReorderToolResults:
    """Test _reorder_tool_results function."""
    
    def test_result_before_use(self):
        """Test tool_result appears before corresponding tool_use."""
        msg1 = MockMsg([{"type": "tool_result", "id": "tool_1", "content": "res1"}])
        msg2 = MockMsg([{"type": "tool_use", "id": "tool_1", "name": "t1", "input": {}}])
        messages = [msg1, msg2]
        
        reordered = _reorder_tool_results(messages)
        assert len(reordered) == 2
        assert reordered[0] == msg2  # tool_use first
        assert reordered[1] == msg1  # then tool_result
    
    def test_result_after_other_message(self):
        """Test tool_result is separated from tool_use by another message."""
        msg1 = MockMsg([{"type": "tool_use", "id": "tool_1", "name": "t1", "input": {}}])
        msg2 = MockMsg("plain text message")
        msg3 = MockMsg([{"type": "tool_result", "id": "tool_1", "content": "res1"}])
        messages = [msg1, msg2, msg3]
        
        reordered = _reorder_tool_results(messages)
        assert len(reordered) == 3
        assert reordered[0] == msg1  # tool_use
        assert reordered[1] == msg3  # tool_result immediately after
        assert reordered[2] == msg2  # plain text comes after
    
    def test_multiple_pairs(self):
        """Test multiple tool_use/result pairs out of order."""
        msg1 = MockMsg([{"type": "tool_result", "id": "tool_1", "content": "res1"}])
        msg2 = MockMsg([{"type": "tool_use", "id": "tool_1", "name": "t1", "input": {}}])
        msg3 = MockMsg([{"type": "tool_result", "id": "tool_2", "content": "res2"}])
        msg4 = MockMsg([{"type": "tool_use", "id": "tool_2", "name": "t2", "input": {}}])
        messages = [msg1, msg2, msg3, msg4]
        
        reordered = _reorder_tool_results(messages)
        assert len(reordered) == 4
        assert reordered[0] == msg2  # tool_1 use
        assert reordered[1] == msg1  # tool_1 result
        assert reordered[2] == msg4  # tool_2 use
        assert reordered[3] == msg3  # tool_2 result
    
    def test_duplicate_ids(self):
        """Test multiple uses of same tool id with multiple results."""
        msg1 = MockMsg([{"type": "tool_result", "id": "tool_1", "content": "res1"}])
        msg2 = MockMsg([{"type": "tool_use", "id": "tool_1", "name": "t1", "input": {}}])
        msg3 = MockMsg([{"type": "tool_result", "id": "tool_1", "content": "res2"}])
        msg4 = MockMsg([{"type": "tool_use", "id": "tool_1", "name": "t1", "input": {}}])
        messages = [msg1, msg2, msg3, msg4]
        
        reordered = _reorder_tool_results(messages)
        assert len(reordered) == 4
        assert reordered[0] == msg2  # first use
        assert reordered[1] == msg1  # first result
        assert reordered[2] == msg4  # second use
        assert reordered[3] == msg3  # second result
    
    def test_no_tool_messages(self):
        """Test messages without any tool blocks - should return unchanged."""
        messages = [
            MockMsg("text1"),
            MockMsg([{"type": "text", "content": "text2"}])
        ]
        reordered = _reorder_tool_results(messages)
        assert reordered == messages
    
    def test_no_results_to_reorder(self):
        """Test messages already in correct order - should return unchanged."""
        messages = [
            MockMsg([{"type": "tool_use", "id": "tool_1", "name": "t1", "input": {}}]),
            MockMsg([{"type": "tool_result", "id": "tool_1", "content": "res1"}]),
            MockMsg("text")
        ]
        reordered = _reorder_tool_results(messages)
        assert reordered == messages


class TestRemoveUnpairedToolMessages:
    """Test _remove_unpaired_tool_messages function."""
    
    def test_unpaired_tool_use(self):
        """Test remove unpaired tool_use."""
        msg1 = MockMsg([{"type": "tool_use", "id": "tool_1", "name": "t1", "input": {}}])
        msg2 = MockMsg("plain text")
        messages = [msg1, msg2]
        
        cleaned = _remove_unpaired_tool_messages(messages)
        assert len(cleaned) == 1
        assert cleaned[0] == msg2  # only plain text remains
    
    def test_unpaired_tool_result(self):
        """Test remove unpaired tool_result."""
        msg1 = MockMsg([{"type": "tool_result", "id": "tool_1", "content": "res1"}])
        msg2 = MockMsg("plain text")
        messages = [msg1, msg2]
        
        cleaned = _remove_unpaired_tool_messages(messages)
        assert len(cleaned) == 1
        assert cleaned[0] == msg2  # only plain text remains
    
    def test_partially_paired(self):
        """Test remove tool_use that has only some results."""
        msg1 = MockMsg([
            {"type": "tool_use", "id": "tool_1", "name": "t1", "input": {}},
            {"type": "tool_use", "id": "tool_2", "name": "t2", "input": {}}
        ])
        msg2 = MockMsg([{"type": "tool_result", "id": "tool_1", "content": "res1"}])
        # Missing result for tool_2
        msg3 = MockMsg("plain text")
        messages = [msg1, msg2, msg3]
        
        cleaned = _remove_unpaired_tool_messages(messages)
        assert len(cleaned) == 1
        assert cleaned[0] == msg3  # both tool messages removed
    
    def test_result_after_other_message(self):
        """Test tool_result separated from tool_use by non-tool message."""
        msg1 = MockMsg([{"type": "tool_use", "id": "tool_1", "name": "t1", "input": {}}])
        msg2 = MockMsg("plain text")  # breaks the pairing
        msg3 = MockMsg([{"type": "tool_result", "id": "tool_1", "content": "res1"}])
        messages = [msg1, msg2, msg3]
        
        cleaned = _remove_unpaired_tool_messages(messages)
        # Both tool messages are removed, only plain text remains
        assert len(cleaned) == 1
        assert msg1 not in cleaned
        assert msg3 not in cleaned
        assert msg2 in cleaned
    
    def test_valid_paired(self):
        """Test valid paired messages are kept."""
        msg1 = MockMsg([{"type": "tool_use", "id": "tool_1", "name": "t1", "input": {}}])
        msg2 = MockMsg([{"type": "tool_result", "id": "tool_1", "content": "res1"}])
        msg3 = MockMsg("plain text")
        messages = [msg1, msg2, msg3]
        
        cleaned = _remove_unpaired_tool_messages(messages)
        assert len(cleaned) == 3
        assert cleaned == messages
    
    def test_multiple_results_for_single_use(self):
        """Test multiple tool_result for one tool_use (valid)."""
        msg1 = MockMsg([{"type": "tool_use", "id": "tool_1", "name": "t1", "input": {}}])
        msg2 = MockMsg([{"type": "tool_result", "id": "tool_1", "content": "part1"}])
        msg3 = MockMsg([{"type": "tool_result", "id": "tool_1", "content": "part2"}])
        messages = [msg1, msg2, msg3]
        
        cleaned = _remove_unpaired_tool_messages(messages)
        assert len(cleaned) == 3
        assert cleaned == messages
    
    def test_orphaned_result_after_valid_pair(self):
        """Test orphaned result after a valid pair is removed."""
        msg1 = MockMsg([{"type": "tool_use", "id": "tool_1", "name": "t1", "input": {}}])
        msg2 = MockMsg([{"type": "tool_result", "id": "tool_1", "content": "res1"}])
        msg3 = MockMsg([{"type": "tool_result", "id": "tool_2", "content": "res2"}])  # orphaned
        messages = [msg1, msg2, msg3]
        
        cleaned = _remove_unpaired_tool_messages(messages)
        assert len(cleaned) == 2
        assert msg3 not in cleaned


class TestDedupToolBlocks:
    """Test _dedup_tool_blocks function."""
    
    def test_duplicate_tool_use_same_message(self):
        """Test duplicate tool_use blocks in same message."""
        msg = MockMsg([
            {"type": "tool_use", "id": "tool_1", "name": "t1", "input": {"a": 1}},
            {"type": "tool_use", "id": "tool_1", "name": "t1", "input": {"a": 2}},  # duplicate
            {"type": "text", "content": "hello"},
            {"type": "tool_use", "id": "tool_2", "name": "t2", "input": {}}
        ])
        messages = [msg]
        
        deduped = _dedup_tool_blocks(messages)
        assert len(deduped) == 1
        assert len(deduped[0].content) == 3
        # Only first tool_1 remains
        assert deduped[0].content[0]["id"] == "tool_1"
        assert deduped[0].content[0]["input"]["a"] == 1
        assert deduped[0].content[1]["type"] == "text"
        assert deduped[0].content[2]["id"] == "tool_2"
    
    def test_no_duplicates(self):
        """Test no duplicate blocks - returns unchanged."""
        msg = MockMsg([
            {"type": "tool_use", "id": "tool_1", "name": "t1", "input": {}},
            {"type": "tool_use", "id": "tool_2", "name": "t2", "input": {}}
        ])
        original_content = msg.content.copy()
        messages = [msg]
        
        deduped = _dedup_tool_blocks(messages)
        assert deduped == messages
        assert deduped[0].content == original_content
    
    def test_duplicates_different_messages(self):
        """Test duplicates in different messages are not removed."""
        msg1 = MockMsg([{"type": "tool_use", "id": "tool_1", "name": "t1", "input": {}}])
        msg2 = MockMsg([{"type": "tool_use", "id": "tool_1", "name": "t1", "input": {}}])
        messages = [msg1, msg2]
        
        deduped = _dedup_tool_blocks(messages)
        assert len(deduped) == 2
        assert deduped == messages  # both kept
    
    def test_duplicate_tool_result(self):
        """Test duplicate tool_result blocks are not removed."""
        msg = MockMsg([
            {"type": "tool_result", "id": "tool_1", "content": "res1"},
            {"type": "tool_result", "id": "tool_1", "content": "res2"}
        ])
        original_content = msg.content.copy()
        messages = [msg]
        
        deduped = _dedup_tool_blocks(messages)
        assert deduped == messages
        assert deduped[0].content == original_content
    
    def test_non_list_content(self):
        """Test messages with non-list content are unchanged."""
        msg = MockMsg("plain text")
        messages = [msg]
        
        deduped = _dedup_tool_blocks(messages)
        assert deduped == messages


class TestRemoveInvalidToolBlocks:
    """Test _remove_invalid_tool_blocks function."""
    
    def test_tool_use_missing_id(self):
        """Test tool_use without id is removed."""
        msg = MockMsg([
            {"type": "tool_use", "name": "t1", "input": {}},  # missing id
            {"type": "tool_use", "id": "tool_2", "name": "t2", "input": {}}
        ])
        messages = [msg]
        
        cleaned = _remove_invalid_tool_blocks(messages)
        assert len(cleaned[0].content) == 1
        assert cleaned[0].content[0]["id"] == "tool_2"
    
    def test_tool_use_empty_id(self):
        """Test tool_use with empty id is removed."""
        msg = MockMsg([
            {"type": "tool_use", "id": "", "name": "t1", "input": {}},  # empty id
            {"type": "tool_use", "id": "tool_2", "name": "t2", "input": {}}
        ])
        messages = [msg]
        
        cleaned = _remove_invalid_tool_blocks(messages)
        assert len(cleaned[0].content) == 1
        assert cleaned[0].content[0]["id"] == "tool_2"
    
    def test_tool_use_none_id(self):
        """Test tool_use with None id is removed."""
        msg = MockMsg([
            {"type": "tool_use", "id": None, "name": "t1", "input": {}},  # None id
            {"type": "tool_use", "id": "tool_2", "name": "t2", "input": {}}
        ])
        messages = [msg]
        
        cleaned = _remove_invalid_tool_blocks(messages)
        assert len(cleaned[0].content) == 1
        assert cleaned[0].content[0]["id"] == "tool_2"
    
    def test_tool_use_missing_name(self):
        """Test tool_use without name is removed."""
        msg = MockMsg([
            {"type": "tool_use", "id": "tool_1", "input": {}},  # missing name
            {"type": "tool_use", "id": "tool_2", "name": "t2", "input": {}}
        ])
        messages = [msg]
        
        cleaned = _remove_invalid_tool_blocks(messages)
        assert len(cleaned[0].content) == 1
        assert cleaned[0].content[0]["id"] == "tool_2"
    
    def test_tool_use_empty_name(self):
        """Test tool_use with empty name is removed."""
        msg = MockMsg([
            {"type": "tool_use", "id": "tool_1", "name": "", "input": {}},  # empty name
            {"type": "tool_use", "id": "tool_2", "name": "t2", "input": {}}
        ])
        messages = [msg]
        
        cleaned = _remove_invalid_tool_blocks(messages)
        assert len(cleaned[0].content) == 1
        assert cleaned[0].content[0]["id"] == "tool_2"
    
    def test_tool_result_missing_id(self):
        """Test tool_result without id is removed."""
        msg = MockMsg([
            {"type": "tool_result", "content": "res1"},  # missing id
            {"type": "tool_result", "id": "tool_2", "content": "res2"}
        ])
        messages = [msg]
        
        cleaned = _remove_invalid_tool_blocks(messages)
        assert len(cleaned[0].content) == 1
        assert cleaned[0].content[0]["id"] == "tool_2"
    
    def test_valid_blocks_kept(self):
        """Test valid blocks are kept."""
        msg = MockMsg([
            {"type": "tool_use", "id": "tool_1", "name": "t1", "input": {}},
            {"type": "tool_result", "id": "tool_1", "content": "res1"},
            {"type": "text", "content": "hello"}
        ])
        original_content = msg.content.copy()
        messages = [msg]
        
        cleaned = _remove_invalid_tool_blocks(messages)
        assert cleaned[0].content == original_content
    
    def test_non_dict_blocks(self):
        """Test non-dict blocks are kept."""
        msg = MockMsg([
            "string block",
            {"type": "tool_use", "id": "tool_1", "name": "t1", "input": {}}
        ])
        messages = [msg]
        
        cleaned = _remove_invalid_tool_blocks(messages)
        assert len(cleaned[0].content) == 2
        assert cleaned[0].content[0] == "string block"
    
    def test_unknown_block_types(self):
        """Test unknown block types are kept."""
        msg = MockMsg([
            {"type": "image", "url": "test.png", "id": "img1"},
            {"type": "tool_use", "id": "tool_1", "name": "t1", "input": {}}
        ])
        original_content = msg.content.copy()
        messages = [msg]
        
        cleaned = _remove_invalid_tool_blocks(messages)
        assert cleaned[0].content == original_content


class TestRepairEmptyToolInputs:
    """Test _repair_empty_tool_inputs function."""
    
    def test_repair_valid_raw_input(self):
        """Test repair tool_use with empty input but valid raw_input."""
        msg = MockMsg([{
            "type": "tool_use",
            "id": "tool_1",
            "name": "t1",
            "input": {},
            "raw_input": '{"param1": "value1", "param2": 123}'
        }])
        messages = [msg]
        
        repaired = _repair_empty_tool_inputs(messages)
        assert repaired[0].content[0]["input"] == {"param1": "value1", "param2": 123}
    
    def test_no_repair_when_input_not_empty(self):
        """Test no repair when input is not empty."""
        original_input = {"param": "value"}
        msg = MockMsg([{
            "type": "tool_use",
            "id": "tool_1",
            "name": "t1",
            "input": original_input,
            "raw_input": '{"param": "different"}'
        }])
        messages = [msg]
        
        repaired = _repair_empty_tool_inputs(messages)
        assert repaired[0].content[0]["input"] == original_input  # unchanged
    
    def test_non_dict_block_in_repair(self):
        """Test non-dict blocks are handled correctly in repair."""
        msg = MockMsg([
            "string block",
            ["list block"],
            {"type": "tool_use", "id": "tool_1", "name": "t1", "input": {}}
        ])
        messages = [msg]
        
        repaired = _repair_empty_tool_inputs(messages)
        assert len(repaired[0].content) == 3
        assert repaired[0].content[0] == "string block"
        assert repaired[0].content[1] == ["list block"]
    
    def test_no_repair_when_raw_input_empty(self):
        """Test no repair when raw_input is empty."""
        msg = MockMsg([{
            "type": "tool_use",
            "id": "tool_1",
            "name": "t1",
            "input": {},
            "raw_input": ""
        }])
        messages = [msg]
        
        repaired = _repair_empty_tool_inputs(messages)
        assert repaired[0].content[0]["input"] == {}  # unchanged
    
    def test_no_repair_when_raw_input_empty_object(self):
        """Test no repair when raw_input is empty object '{}'."""
        msg = MockMsg([{
            "type": "tool_use",
            "id": "tool_1",
            "name": "t1",
            "input": {},
            "raw_input": "{}"
        }])
        messages = [msg]
        
        repaired = _repair_empty_tool_inputs(messages)
        assert repaired[0].content[0]["input"] == {}  # unchanged
    
    def test_invalid_json_raw_input(self):
        """Test raw_input with invalid JSON is not repaired."""
        msg = MockMsg([{
            "type": "tool_use",
            "id": "tool_1",
            "name": "t1",
            "input": {},
            "raw_input": '{"param": "value", missing closing}'
        }])
        messages = [msg]
        
        repaired = _repair_empty_tool_inputs(messages)
        assert repaired[0].content[0]["input"] == {}  # unchanged
    
    def test_raw_input_not_dict(self):
        """Test raw_input that parses to non-dict is not repaired."""
        msg = MockMsg([{
            "type": "tool_use",
            "id": "tool_1",
            "name": "t1",
            "input": {},
            "raw_input": '["value1", "value2"]'  # list, not dict
        }])
        messages = [msg]
        
        repaired = _repair_empty_tool_inputs(messages)
        assert repaired[0].content[0]["input"] == {}  # unchanged
    
    def test_no_raw_input_field(self):
        """Test tool_use without raw_input field is unchanged."""
        msg = MockMsg([{
            "type": "tool_use",
            "id": "tool_1",
            "name": "t1",
            "input": {}
            # no raw_input
        }])
        messages = [msg]
        
        repaired = _repair_empty_tool_inputs(messages)
        assert repaired[0].content[0]["input"] == {}  # unchanged


class TestSanitizeToolMessages:
    """Test _sanitize_tool_messages function."""
    
    def test_already_valid_messages(self):
        """Test valid messages are returned unchanged."""
        messages = [
            MockMsg([{"type": "tool_use", "id": "tool_1", "name": "t1", "input": {}}]),
            MockMsg([{"type": "tool_result", "id": "tool_1", "content": "res1"}]),
            MockMsg("plain text")
        ]
        sanitized = _sanitize_tool_messages(messages)
        assert sanitized == messages
    
    def test_pending_tool_use_without_result(self):
        """Test pending tool_use without result triggers sanitization."""
        messages = [
            MockMsg([{"type": "tool_use", "id": "tool_1", "name": "t1", "input": {}}]),
            MockMsg("plain text")  # no result follows
        ]
        sanitized = _sanitize_tool_messages(messages)
        # The unpaired tool_use should be removed
        assert len(sanitized) == 1
        assert "plain text" in sanitized[0].content
    
    def test_complex_scenario(self):
        """Test complex scenario with multiple issues."""
        # Scenario:
        # 1. Result before use
        # 2. Invalid tool_use (missing name)
        # 3. Duplicate tool_use
        # 4. Unpaired tool_use
        msg1 = MockMsg([{"type": "tool_result", "id": "tool_1", "content": "res1"}])
        msg2 = MockMsg([
            {"type": "tool_use", "id": "tool_1", "input": {}},  # missing name - invalid
            {"type": "tool_use", "id": "tool_1", "name": "t1", "input": {}},  # duplicate
            {"type": "tool_use", "id": "tool_2", "name": "t2", "input": {}}  # valid
        ])
        msg3 = MockMsg([{"type": "tool_result", "id": "tool_2", "content": "res2"}])
        msg4 = MockMsg([{"type": "tool_use", "id": "tool_3", "name": "t3", "input": {}}])  # unpaired
        messages = [msg1, msg2, msg3, msg4]
        
        sanitized = _sanitize_tool_messages(messages)
        
        # Should keep:
        # - tool_1 use (valid one, deduped) + result
        # - tool_2 use + result
        # msg4 is removed (unpaired)
        assert len(sanitized) == 3
        # Check order: tool_1 and tool_2 uses, tool_1 result, tool_2 result
        uses1, results1 = extract_tool_ids(sanitized[0])
        assert uses1 == {"tool_1", "tool_2"}  # both uses in same message
        uses2, results2 = extract_tool_ids(sanitized[1])
        assert results2 == {"tool_1"}
        uses3, results3 = extract_tool_ids(sanitized[2])
        assert results3 == {"tool_2"}
    
    def test_empty_messages(self):
        """Test empty messages list."""
        assert _sanitize_tool_messages([]) == []
    
    def test_no_tool_messages(self):
        """Test messages without tool blocks."""
        messages = [MockMsg("text1"), MockMsg("text2")]
        assert _sanitize_tool_messages(messages) == messages


class TestTruncateText:
    """Test _truncate_text function."""
    
    def test_short_text_no_truncation(self):
        """Test text shorter than max_length is unchanged."""
        text = "Hello, world!"
        assert _truncate_text(text, 20) == text
    
    def test_exact_length_no_truncation(self):
        """Test text exactly max_length is unchanged."""
        text = "a" * 100
        assert _truncate_text(text, 100) == text
    
    def test_long_text_truncated(self):
        """Test text longer than max_length is truncated."""
        text = "a" * 200
        result = _truncate_text(text, 100)
        assert len(result) < 200
        assert result.startswith("a" * 50)  # first half
        assert result.endswith("a" * 50)  # last half
        assert "[...truncated 100 chars...]" in result
    
    def test_odd_max_length(self):
        """Test max_length is odd number."""
        text = "a" * 101
        result = _truncate_text(text, 51)
        assert len(result) < 101
        assert result.startswith("a" * 25)  # 51//2 = 25
        assert result.endswith("a" * 25)
    
    def test_empty_text(self):
        """Test empty string input."""
        assert _truncate_text("", 100) == ""
    
    def test_none_text(self):
        """Test None input."""
        assert _truncate_text(None, 100) == ""
    
    def test_non_string_input(self):
        """Test non-string input (numbers, objects)."""
        assert _truncate_text(12345, 10) == "12345"
        # Float 3.14159 becomes "3.14159" (6 chars), max_length 4 will truncate
        result = _truncate_text(3.14159, 4)
        assert "3." in result
        assert "59" in result
        assert "[...truncated 3 chars...]" in result
    
    def test_truncation_message_accuracy(self):
        """Test truncated count is accurate."""
        original_length = 1000
        max_length = 200
        text = "a" * original_length
        result = _truncate_text(text, max_length)
        expected_truncated = original_length - max_length
        assert f"[...truncated {expected_truncated} chars...]" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
