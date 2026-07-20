"""
Copyright 2026 Akamai Technologies, Inc. All Rights Reserved.

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

from enum import StrEnum


class EdgeHostnameMode(StrEnum):
    USE_EXISTING_EDGEHOSTNAME = 'use_existing_edgehostname'
    SECURE_BY_DEFAULT = 'secure_by_default'
    NEW_STANDARD_TLS_EDGEHOSTNAME = 'new_standard_tls_edgehostname'
    NEW_ENHANCED_TLS_EDGEHOSTNAME = 'new_enhanced_tls_edgehostname'
    CREATE_CPS_EDGEHOSTNAME = 'create_cps_edgehostname'
    CPS_PLACEHOLDER = 'cps_placeholder'
