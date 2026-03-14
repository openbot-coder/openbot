from openbot.agents.buildin_tools.send_file import _auto_as_type


def test_auto_as_type():
    # Test image types
    assert _auto_as_type("image/png") == "image"
    assert _auto_as_type("image/jpeg") == "image"
    assert _auto_as_type("image/gif") == "image"
    
    # Test audio types
    assert _auto_as_type("audio/mpeg") == "audio"
    assert _auto_as_type("audio/wav") == "audio"
    assert _auto_as_type("audio/ogg") == "audio"
    
    # Test video types
    assert _auto_as_type("video/mp4") == "video"
    assert _auto_as_type("video/mov") == "video"
    assert _auto_as_type("video/avi") == "video"
    
    # Test text types
    assert _auto_as_type("text/plain") == "text"
    assert _auto_as_type("text/markdown") == "text"
    assert _auto_as_type("text/html") == "text"
    
    # Test other types
    assert _auto_as_type("application/json") == "file"
    assert _auto_as_type("application/pdf") == "file"
    assert _auto_as_type("application/octet-stream") == "file"
