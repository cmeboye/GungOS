"""Boot and SD migration checks after removing retired upstream services."""
import os,sys
from time import ticks_ms
root=os.getcwd()
sys.path.insert(0,root+'/src/MicroPython')
sys.path.insert(0,root+'/simulator/hardware')
import sim_runtime
sim_runtime.configure(root,'/private/tmp/gungos-independent-test-'+str(ticks_ms()),root+'/builds/MicroPython/apps_unfrozen',1,'picocalc-pico2w',0,True,False,False,False,'',_network_mode='offline',_audio_mode='silent',_sd_profile='clean')
from picoware.system.view_manager import ViewManager
from picoware.system.settings import Settings,RETIRED_SERVICE_SETTINGS
from picoware.system.view import View
from picoware.applications import desktop,settings as settings_app
from picoware.system.http import HTTP
from picoware.system.time import Time
vm=ViewManager();storage=vm.storage;path='picoware/settings/picoware.json'
assert not any(key in Settings(storage).settings for key in RETIRED_SERVICE_SETTINGS)
# Simulate a card from the upstream firmware; none of these values are real credentials.
legacy={key:'synthetic-retired-account' for key in RETIRED_SERVICE_SETTINGS}
legacy.update({'wifi_ssid':'Independent AP','wifi_password':'','theme_color':0xF800,'custom_field':'keep'})
assert storage.serialize(legacy,path)
loaded=Settings(storage)
assert not any(key in loaded.settings for key in RETIRED_SERVICE_SETTINGS)
assert loaded.wifi_settings=={'ssid':'Independent AP','password':''}
assert storage.deserialize(path)==legacy,'Loading preferences must not rewrite the SD'
assert loaded.update({'screen_brightness':40})
saved=storage.deserialize(path)
assert not any(key in saved for key in RETIRED_SERVICE_SETTINGS)
assert saved['custom_field']=='keep' and saved['theme_color']==0xF800
assert saved['wifi_ssid']=='Independent AP' and saved['screen_brightness']==40
assert loaded.update({key:'synthetic-retired-account' for key in RETIRED_SERVICE_SETTINGS})
assert not any(key in storage.deserialize(path) for key in RETIRED_SERVICE_SETTINGS)
for key in RETIRED_SERVICE_SETTINGS:assert Settings.get(storage,key,'absent')=='absent'
# Old per-field account files must never be imported into fresh settings.
for name,field in [('server_username','username'),('server_password','password')]:
 assert storage.serialize({field:'synthetic-legacy-account'},'picoware/settings/'+name+'.json')
storage.remove(path)
fresh=Settings(storage)
assert not any(key in fresh.settings for key in RETIRED_SERVICE_SETTINGS)
assert settings_app.start(vm)
assert not settings_app._menu.item_exists('Server Settings')
assert not any('jblanked' in str(item).lower() for item in settings_app.__config())
settings_app.stop(vm)
print('PASS: upstream account defaults/editors/migration removed; ordinary settings and Wi-Fi survive')

for name in ('picoware.applications.notifications','picoware.applications.applications.FlipSocial','picoware.applications.applications.app_store','picoware.applications.system.update'):
 try:__import__(name,None,None,['start'])
 except ImportError:pass
 else:raise AssertionError('Retired service remains importable: '+name)
print('PASS: social, notification, App Store and upstream updater clients cannot be imported')

import network
network.sim_clear_aps();network.sim_add_ap('Independent AP',passphrase='')
assert Settings(storage).save_wifi_settings({'ssid':'Independent AP','password':''})
http_init=HTTP.__init__;time_fetch=Time.fetch;time_requests=[]
def no_http(self,*args,**kwargs):raise AssertionError('Home opened an HTTP client')
def time_only(self,offset=0):time_requests.append(offset);self._requested=True;return True
HTTP.__init__=no_http;Time.fetch=time_only
vm.time._is_set=False;vm.time._requested=False
try:
 vm.add(View('desktop_view',desktop.run,desktop.start,desktop.stop));vm.switch_to('desktop_view')
 for _ in range(5):vm.run()
 assert vm.wifi.is_connected() and len(time_requests)==1
finally:
 desktop.stop(vm);HTTP.__init__=http_init;Time.fetch=time_fetch
print('PASS: independent home reconnects without an HTTP client; only the retained NTP path is requested')
