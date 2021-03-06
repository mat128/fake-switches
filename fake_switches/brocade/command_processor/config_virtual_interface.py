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

from netaddr import IPNetwork

from fake_switches.brocade.command_processor.config_interface import ConfigInterfaceCommandProcessor
from fake_switches.brocade.command_processor.config_virtual_interface_vrrp import \
    ConfigVirtualInterfaceVrrpCommandProcessor


class ConfigVirtualInterfaceCommandProcessor(ConfigInterfaceCommandProcessor):
    def get_prompt(self):
        return "SSH@%s(config-vif-%s)#" % (self.switch_configuration.name, self.port.vlan_id)

    def do_ip(self, *args):
        if "address".startswith(args[0]):
            new_ip = IPNetwork(args[1])
            ip_owner, existing_ip = self.switch_configuration.get_port_and_ip_by_ip(new_ip.ip)
            if not ip_owner:
                self.port.add_ip(new_ip)
            else:
                if ip_owner == self.port:
                    for ip in self.port.ips:
                        if new_ip.ip == ip.ip:
                            self.write_line("IP/Port: Errno(6) Duplicate ip address")
                            break
                        else:
                            if new_ip.ip in ip:
                                if len(args) > 2 and "secondary".startswith(args[2]):
                                    if not next((ip for ip in self.port.secondary_ips if ip.ip == new_ip.ip), False):
                                        self.port.add_secondary_ip(new_ip)
                                    else:
                                        self.write_line("IP/Port: Errno(6) Duplicate ip address")
                                        break
                                else:
                                    self.write_line(
                                        "IP/Port: Errno(15) Can only assign one primary ip address per subnet")
                                    break
                else:
                    self.write_line("IP/Port: Errno(11) ip subnet overlap with another interface")

        if "access-group".startswith(args[0]):
            if "in".startswith(args[2]):
                self.port.access_group_in = args[1]
            elif "out".startswith(args[2]):
                self.port.access_group_out = args[1]

        if "vrrp-extended".startswith(args[0]):
            if "vrid".startswith(args[1]):
                group = args[2]
                vrrp = self.port.get_vrrp_group(group)
                if vrrp is None:
                    vrrp = self.switch_configuration.new("VRRP", group)
                    self.port.vrrps.append(vrrp)
                self.move_to(ConfigVirtualInterfaceVrrpCommandProcessor, self.port, vrrp)

            if "auth-type".startswith(args[1]):
                if "simple-text-auth".startswith(args[2]):
                    self.port.vrrp_common_authentication = args[3]
                elif "no-auth".startswith(args[2]):
                    self.port.vrrp_common_authentication = None

    def do_no_ip(self, *args):
        if "address".startswith(args[0]):
            deleting_ip = IPNetwork(args[1])
            if next((ip for ip in self.port.secondary_ips if ip.ip == deleting_ip.ip), False):
                self.port.remove_secondary_ip(deleting_ip)
            else:
                if not next((ip for ip in self.port.secondary_ips if ip in deleting_ip), False):
                    self.port.remove_ip(deleting_ip)
                else:
                    self.write_line("IP/Port: Errno(18) Delete secondary address before deleting primary address")
        if "access-group".startswith(args[0]):
            if len(args) < 3:
                self.write_line("Error: Wrong Access List Name %s" % args[1])
            else:
                if "in".startswith(args[2]):
                    if self.port.access_group_in == args[1]:
                        self.port.access_group_in = None
                    else:
                        self.write_line("Error: Wrong Access List Name %s" % args[1])
                elif "out".startswith(args[2]):
                    if self.port.access_group_out == args[1]:
                        self.port.access_group_out = None
                    else:
                        self.write_line("Error: Wrong Access List Name %s" % args[1])

        if "vrrp-extended".startswith(args[0]):
            if "vrid".startswith(args[1]):
                group = args[2]
                vrrp = self.port.get_vrrp_group(group)
                if vrrp:
                    self.port.vrrps.remove(vrrp)

            if "auth-type".startswith(args[1]):
                if "simple-text-auth".startswith(args[2]) and len(args) == 4:
                    self.do_ip(*"vrrp-extended auth-type no-auth".split())
                else:
                    self.write_line("Incomplete command.")
