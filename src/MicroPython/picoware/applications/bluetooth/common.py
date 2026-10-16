"""Bounded scan results shared by the built-in BLE views."""
def add_result(bluetooth,menu,devices,addresses,data,connectable_only=False):
    addr_type,addr,adv_type,rssi,adv=data
    key=(addr_type,bytes(addr))
    if connectable_only and (adv_type not in (0,1,4) or (adv_type==4 and key not in addresses)):return
    name=bluetooth.decode_name(adv)
    if key in addresses:
        index=addresses.index(key);previous=devices[index]
        # Active scans may alternate a shortened advertisement and full scan response.
        if not name or (previous[2] and previous[2].startswith(name)):name=previous[2]
        devices[index]=(addr_type,bytes(addr),name,rssi)
        if menu is not None:menu.items[index]=(name or ':'.join('%02X'%b for b in addr))+' ('+str(rssi)+'dB)'
        return
    if len(devices)>=64:return
    addresses.append(key);devices.append((addr_type,bytes(addr),name,rssi))
    if menu is not None:menu.add_item((name or ':'.join('%02X'%b for b in addr))+' ('+str(rssi)+'dB)')
