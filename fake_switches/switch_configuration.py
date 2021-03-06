# Copyright 2015 Internap.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import re

class SwitchConfiguration(object):
    def __init__(self, ip, name="", auto_enabled=False, privileged_passwords=None, ports=None, vlans=None, objects_overrides=None):
        self.ip = ip
        self.name = name
        self.privileged_passwords = privileged_passwords or []
        self.auto_enabled = auto_enabled
        self.vlans = []
        self.ports = []
        self.vrfs = [VRF('DEFAULT-LAN')]
        self.locked = False
        self.objects_factory = {
            "VRF": VRF,
            "Vlan": Vlan,
            "Port": Port,
            "VRRP": VRRP,
            "VlanPort": VlanPort,
            "AggregatedPort": AggregatedPort,
        }

        if vlans:
            [self.add_vlan(v) for v in vlans]
        if ports:
            [self.add_port(p) for p in ports]
        if objects_overrides:
            self.objects_factory.update(objects_overrides)

    def new(self, class_name, *args, **kwargs):
        return self.objects_factory[class_name](*args, **kwargs)

    def get_vlan(self, number):
        return next((vlan for vlan in self.vlans if vlan.number == number), None)

    def get_vlan_by_name(self, name):
        return next((vlan for vlan in self.vlans if vlan.name == name), None)

    def add_vlan(self, vlan):
        self.vlans.append(vlan)
        vlan.switch_configuration = self

    def remove_vlan(self, vlan):
        vlan.switch_configuration = None
        self.vlans.remove(vlan)

    def get_port(self, name):
        return next((port for port in self.ports if port.name == name), None)

    def add_port(self, port):
        self.ports.append(port)
        port.switch_configuration = self

    def remove_port(self, port):
        port.switch_configuration = None
        self.ports.remove(port)

    def get_port_by_partial_name(self, name):
        partial_name, number = split_port_name(name.lower())

        return next((port for port in self.ports if port.name.lower().startswith(partial_name.strip()) and port.name.lower().endswith(number.strip())), None)

    def get_port_and_ip_by_ip(self, ip_string):
        for port in filter(lambda e: isinstance(e, VlanPort), self.ports):
            for ip in port.ips:
                if ip_string in ip:
                    return port, ip
        return None, None

    def add_vrf(self, vrf):
        if not self.get_vrf(vrf.name):
            self.vrfs.append(vrf)

    def get_vrf(self, name):
        return next((vrf for vrf in self.vrfs if vrf.name == name), None)

    def remove_vrf(self, name):
        vrf = self.get_vrf(name)
        if vrf:
            self.vrfs.remove(vrf)
            for port in self.ports:
                if port.vrf and port.vrf.name == name:
                    port.vrf = None


class VRF(object):
    def __init__(self, name):
        self.name = name


class Vlan(object):
    def __init__(self, number=None, name=None, description=None, switch_configuration=None):
        self.number = number
        self.name = name
        self.description = description
        self.switch_configuration = switch_configuration


class Port(object):
    def __init__(self, name):
        self.name = name
        self.switch_configuration = None
        self.description = None
        self.mode = None
        self.access_vlan = None
        self.trunk_vlans = None
        self.trunk_native_vlan = None
        self.trunk_encapsulation_mode = None
        self.shutdown = None
        self.vrf = None
        self.speed = None
        self.auto_negotiation = None
        self.aggregation_membership = None
        self.vendor_specific = {}

    def reset(self):
        self.description = None
        self.mode = None
        self.access_vlan = None
        self.trunk_vlans = None
        self.trunk_native_vlan = None
        self.shutdown = None
        self.vrf = None
        self.speed = None
        self.auto_negotiation = None
        self.aggregation_membership = None
        self.vendor_specific = {}

    def get_subname(self, length):
        name, number = split_port_name(self.name)
        return name[:length] + number


class VRRP(object):
    def __init__(self, group_id):
        self.group_id = group_id
        self.ip_addresses = None
        self.description = None
        self.authentication = None
        self.timers_hello = None
        self.timers_hold = False
        self.priority = None
        self.track = {}
        self.preempt = True
        self.preempt_delay_minimum = None
        self.activated = None
        self.advertising = None


class VlanPort(Port):
    def __init__(self, vlan_id, *args, **kwargs):
        super(VlanPort, self).__init__(*args, **kwargs)

        self.vlan_id = vlan_id
        self.access_group_in = None
        self.access_group_out = None
        self.ips = []
        self.secondary_ips = []
        self.vrrp_common_authentication = None
        self.vrrps = []

    def get_vrrp_group(self, group):
        return next((vrrp for vrrp in self.vrrps if vrrp.group_id==group), None)

    def add_ip(self, ip_network):
        existing_ip = next((ip for ip in self.ips if ip.ip == ip_network.ip), None)
        if existing_ip:
            self.ips[self.ips.index(existing_ip)] = ip_network
        else:
            self.ips.append(ip_network)

    def add_secondary_ip(self, ip_network):
        self.secondary_ips.append(ip_network)

    def remove_ip(self, ip_network):
        for i, ip in enumerate(self.ips):
            if ip.ip == ip_network.ip:
                self.ips.pop(i)
                break

    def remove_secondary_ip(self, deleting_ip):
        ip = next((ip for ip in self.secondary_ips if ip.ip == deleting_ip.ip), None)
        if ip:
            self.secondary_ips.remove(ip)


class AggregatedPort(Port):
    def __init__(self, *args, **kwargs):
        super(AggregatedPort, self).__init__(*args, **kwargs)

        self.lacp_active = False
        self.lacp_periodic = None

    def get_child_ports_linked_to_a_machine(self):
        return [p for p in self.switch_configuration.ports if p.aggregation_membership == self.name and p.link_name is not None]


def split_port_name(name):
    number_start, number_len = re.compile('\d').search(name).span()
    return name[0:number_start], name[number_start:]
