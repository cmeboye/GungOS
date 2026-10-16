"""Run from the repo root with builds/MicroPython/desktop/micropython -X heapsize=16M simulator/test_ai_setup.py."""

import os
import sys
from time import sleep, ticks_ms

root = os.getcwd()
sys.path.insert(0, root + '/src/MicroPython')
sys.path.insert(0, root + '/simulator/hardware')
import sim_runtime
sd_root = '/private/tmp/picoware-ai-regression-' + str(ticks_ms())
sim_runtime.configure(root, sd_root, root + '/builds/MicroPython/apps_unfrozen',
                      1, 'picocalc-pico2w', 0, True, False, False, False, '',
                      _network_mode='offline', _audio_mode='silent')
sim_runtime.mkdir_p(sd_root)
import network
network.sim_clear_aps()
network.sim_add_ap('Lab (2.4 GHz)', passphrase='test-pass', rssi=-30)
from picoware.system.view_manager import ViewManager
from picoware.system.view import View
from picoware.system.settings import Settings
from picoware.applications.wifi import scan, password, ssid, connect, utils
from picoware.system.input import Input
def simulator_input(self):
    sim_runtime.input_polled()
    return self._last_button
# Use the same PicoCalc input hook as simulator/run.py.
Input.button = property(simulator_input)


from picoware.applications import settings as settings_app, ai_setup as ai
from picoware.system.buttons import BUTTON_CENTER, BUTTON_BACK
from picoware.system.agent.llm import OPENAI, LOCAL, CUSTOM
from picoware.system.http import HTTP
vm = ViewManager()
alerts = []
ViewManager.alert = lambda self, message, *args: alerts.append(message)
Settings(vm.storage).update({'openai_api_key': 'test-key', 'deepseek_api_key': 'other-test-key'})
vm.add(View('settings', settings_app.run, settings_app.start, settings_app.stop))
vm.switch_to('settings')
labels = settings_app._menu.list.items
assert labels[0] == 'AI Setup'
assert not any('API Key' in label for label in labels)
# Verify filtered menu indices still refer to the correct device setting.
settings_app._menu.set_selected(labels.index('Dark Mode'))
vm._button = BUTTON_CENTER
settings_app.run(vm)
assert settings_app._current_setting == settings_app.STATE_DARK_MODE
vm._button = BUTTON_BACK
settings_app.run(vm)
settings_app._menu.set_selected(0)
vm._button = BUTTON_CENTER
settings_app.run(vm)
assert vm._current_view.name == 'ai_setup'
assert ai._key() == 'other-test-key'
assert ai._save_config({'provider': OPENAI, 'model': 'test-model'})
ai._show_menu()
assert ai._menu.get_item(1) == 'API Key: Configured'
ai._edit('key')
assert vm.keyboard.secret and vm.keyboard.response == 'test-key'
# The rendered key should be masked; raw credentials remain available for editing.
texts=[]
from picoware.gui.draw import Draw
original_text=Draw._text
Draw._text=lambda self, x, y, value, *args: texts.append(value)
vm.keyboard._draw_textbox()
Draw._text=original_text
assert not any('test-key' in text for text in texts)
assert any('*' in text for text in texts)
assert vm.keyboard._auto_complete_suggestions() == ()
assert ai._save_field('replacement-key')
assert Settings(vm.storage).openai_api_key == 'replacement-key'
assert Settings(vm.storage).deepseek_api_key == 'other-test-key'
vm.keyboard.reset()
assert not vm.keyboard.secret
assert ai._save_config({'provider': LOCAL, 'model': 'local-model'})
ai._show_advanced()
assert 'Server URL' in ai._options
ai._field = 'url'
assert not ai._save_field('invalid-url')
assert ai._save_field('http://192.168.1.20:8080/v1/chat/completions')
assert ai._save_custom({'url':'http://192.168.1.20:8080/v1/chat/completions', 'api_key':'', 'models':['custom-model']})
assert ai._save_config({'provider':CUSTOM, 'model':'custom-model'})
assert ai._llm().url.startswith('http://192.168.1.20')
# Failed writes keep editor/config values and leave persisted keys intact.
class FailingStorage:
    def __init__(self, backing): self.backing = backing
    def exists(self, path): return self.backing.exists(path)
    def read(self, path): return self.backing.read(path)
    def serialize(self, value, path): return False
    def mkdir(self, path): return True
backing = vm._storage
vm._storage = FailingStorage(backing)
ai._settings._storage = vm._storage
previous = ai._config.copy()
assert not ai._save_config({'provider':OPENAI})
assert ai._config == previous
ai._config['provider'] = OPENAI
ai._field='key'
assert not ai._save_field('discarded-key')
assert ai._settings.openai_api_key == 'replacement-key'
assert Settings(backing).openai_api_key == 'replacement-key'
vm._storage = backing
ai._settings._storage = backing
assert ai._save_config({'provider':OPENAI, 'model':'test-model'})
class TestWiFi:
    def is_connected(self): return True
vm._wifi = TestWiFi()
class TestHTTP:
    last = None
    def __init__(self, **kwargs): self.response = None; self.closed=False; TestHTTP.last=self
    def post_async(self, url, payload, **kwargs): self.url=url; self.payload=payload; self.headers=kwargs['headers']; return True
    def close(self): self.closed=True
    def is_request_complete(self): return self.response is not None
import picoware.system.http as http_module
http_module.HTTP = TestHTTP
class Response:
    def __init__(self, status, body): self.status_code=status; self.body=body
    def json(self): return self.body
ai._start_test()
assert ai._mode == 'testing'
assert TestHTTP.last.payload['max_completion_tokens'] == 64
assert TestHTTP.last.headers['Authorization'] == 'Bearer replacement-key'
TestHTTP.last.response = Response(200, {'choices':[{'message':{'content':'OK'}}]})
vm._button=-1
ai.run(vm)
assert ai._mode == 'result' and TestHTTP.last.closed
assert 'successful' in ai._test_result(TestHTTP.last.response)
assert 'Authentication' in ai._test_result(Response(401, {}))
assert 'quota' in ai._test_result(Response(429, {}))
assert 'model' in ai._test_result(Response(404, {}))
assert 'did not return' in ai._test_result(Response(200, {}))
assert 'No response' in ai._test_result(None)
ai._start_test()
vm._button=BUTTON_BACK
ai.run(vm)
assert TestHTTP.last.closed and ai._mode == 'menu'
http_module.HTTP = HTTP
# MCP settings return to shared setup, and save credentials through checked writes.
ai._show_advanced()
ai._menu.set_selected(ai._options.index('MCP Servers'))
vm._button=BUTTON_CENTER
ai.run(vm)
assert vm._current_view.name == 'ai_mcp'
assert settings_app.__add_mcp_server('http://192.168.1.20/mcp')
settings_app._mcp_server_index=0
assert settings_app.__save_mcp_api_key('mcp-test-key')
vm._button=BUTTON_BACK
settings_app.run(vm)
assert vm._current_view.name == 'ai_setup'
assert Settings(backing).mcp_servers[0]['api_key'] == 'mcp-test-key'
assert ai._config['provider'] == OPENAI and ai._config['model'] == 'test-model'
assert Settings(backing).deepseek_api_key == 'other-test-key'
# Agent uses this same setup screen; importing it also checks simulator decorators.
from picoware.applications.applications import agent
assert agent.start(vm)
agent._menu.set_selected(3)
vm._button=BUTTON_CENTER
agent.run(vm)
assert vm._current_view.name == 'ai_setup'
vm.draw.screenshot('/private/tmp/picoware-ai-setup.bmp')
print('PASS: menus, provider/model persistence, key masking, and credential preservation')
print('PASS: failed writes, custom/local URL validation, and MCP round trip')
print('PASS: connection request, success/errors/cancel, and shared Agent setup')
ai.stop(vm)
