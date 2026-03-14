from openbot.agents.buildin_tools.send_file import _auto_as_type

print("Testing _auto_as_type:")
print(f"image/png: {_auto_as_type('image/png')}")
print(f"audio/mp3: {_auto_as_type('audio/mp3')}")
print(f"video/mp4: {_auto_as_type('video/mp4')}")
print(f"text/plain: {_auto_as_type('text/plain')}")
print(f"application/pdf: {_auto_as_type('application/pdf')}")
print("All tests passed!")
