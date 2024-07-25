"""
Copyright 2022 Akamai Technologies, Inc. All Rights Reserved.

 Licensed under the Apache License, Version 2.0 (the "License");
 you may not use this file except in compliance with the License.
 You may obtain a copy of the License at
    http://www.apache.org/licenses/LICENSE-2.0
 Unless required by applicable law or agreed to in writing, software
 distributed under the License is distributed on an "AS IS" BASIS,
 WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 See the License for the specific language governing permissions and
 limitations under the License.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from dataclasses import field

from exceptions import setup_logger


logger = setup_logger()


@dataclass
class AppSec:
    waf_config_name: str
    onboard_waf_config_id: int
    onboard_waf_config_version: int
    notification_emails: list[str] = field(default_factory=list)

    activation_id: int = 0
    activation_status: str = ''
    activation_create: str = ''
    activation_end: str = ''
    version_notes: str = ''


@dataclass
class Property:
    contract_id: str
    group_id: str
    waf_config_name: str
    policy_name: list

    public_hostnames: list[str] = field(default_factory=list)
    waf_target_hostnames: list[str] = field(default_factory=list)
    property_name: str = ''
    target_id: int = 0
    version_notes: str = ''
    onboard_waf_config_id: int = 0
    onboard_waf_config_version: int = 0

    notification_emails: list[str] = field(default_factory=list)


@dataclass
class Generic:
    contract_id: str
    group_id: str
    csv: str
    template: str

    network: str = 'staging'
    notification_emails: list = field(default_factory=lambda: ['noreply@akamai.com'])
    activate: str = None
    version_notes: str = None
