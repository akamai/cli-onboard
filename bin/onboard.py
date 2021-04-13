"""
Copyright 2019 Akamai Technologies, Inc. All Rights Reserved.

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
import os

class onboard(object):
    #Initialize the object
    def __init__(self, setup_json_content, config):
        #Read values from setup.json or --file
        #Certain values (onboard_) are updated in main processing later
        try:
            self.property_name = setup_json_content['property_info']['property_name']
            self.secure_network = setup_json_content['property_info']['secure_network']
            self.contract_id = setup_json_content['property_info']['contract_id']
            self.group_id = setup_json_content['property_info']['group_id']
            self.product_id = setup_json_content['property_info']['product_id']
            self.rule_format = setup_json_content['property_info']['rule_format']
            self.create_new_cpcode = setup_json_content['property_info']['default_cpcode']['create_new_cpcode']
            self.new_cpcode_name = setup_json_content['property_info']['default_cpcode']['new_cpcode_name']
            self.use_file = setup_json_content['property_info']['file_info']['use_file']
            self.source_template_file = setup_json_content['property_info']['file_info']['source_template_file']
            self.source_values_file = setup_json_content['property_info']['file_info']['source_values_file']
            self.use_folder = setup_json_content['property_info']['folder_info']['use_folder']
            self.folder_path = setup_json_content['property_info']['folder_info']['folder_path']
            self.env_name = setup_json_content['property_info']['folder_info']['env_name']

            self.public_hostnames = setup_json_content['public_hostnames']
            
            self.onboard_property_id = None
            self.onboard_default_cpcode = 0
            self.edge_hostname_id = 0
            
            #Edge hostname values
            self.edge_hostname_mode = setup_json_content['edge_hostname']['mode']
            self.edge_hostname = setup_json_content['edge_hostname']['use_existing_edgehostname']['edge_hostname']
            self.use_existing_enrollment_id = setup_json_content['edge_hostname']['new_enhanced_tls_edgehostname']['ssl_cert_info']['use_existing_enrollment_id']
            self.existing_enrollment_id = setup_json_content['edge_hostname']['new_enhanced_tls_edgehostname']['ssl_cert_info']['existing_enrollment_id']
            self.existing_slot_number = setup_json_content['edge_hostname']['new_enhanced_tls_edgehostname']['ssl_cert_info']['existing_slot_number']
            self.create_new_ssl_cert = setup_json_content['edge_hostname']['new_enhanced_tls_edgehostname']['ssl_cert_info']['create_new_ssl_cert']
            self.ssl_cert_template_file = setup_json_content['edge_hostname']['new_enhanced_tls_edgehostname']['ssl_cert_info']['ssl_cert_template_file']
            self.ssl_cert_template_values = setup_json_content['edge_hostname']['new_enhanced_tls_edgehostname']['ssl_cert_info']['ssl_cert_template_values']
            self.temp_existing_edge_hostname = setup_json_content['edge_hostname']['new_enhanced_tls_edgehostname']['ssl_cert_info']['temp_existing_edge_hostname']

            #WAF values
            self.add_selected_host = setup_json_content['update_waf_info']['add_selected_host']
            self.waf_config_name = setup_json_content['update_waf_info']['waf_config_name']
            self.update_match_target = setup_json_content['update_waf_info']['update_match_target']
            self.waf_match_target_id = setup_json_content['update_waf_info']['waf_match_target_id']

            self.onboard_waf_config_id = None
            self.onboard_waf_config_version = None
            self.onboard_waf_prev_version = None

            #Activation values
            self.activate_property_staging = setup_json_content['activate_property_staging']
            self.activate_waf_policy_staging = setup_json_content['activate_waf_policy_staging']
            self.activate_property_production = setup_json_content['activate_property_production']
            self.activate_waf_policy_production = setup_json_content['activate_waf_policy_production']
            self.notification_emails = setup_json_content['notification_emails']

            #Read config object that contains the command line parameters
            if not config.edgerc:
                if not os.getenv("AKAMAI_EDGERC"):
                    self.edgerc = os.path.join(os.path.expanduser("~"), '.edgerc')
                else:
                    self.edgerc = os.getenv("AKAMAI_EDGERC")
            else:
                self.edgerc = config.edgerc

            if not config.section:
                if not os.getenv("AKAMAI_EDGERC_SECTION"):
                    self.section = "onboard"
                else:
                    self.section = os.getenv("AKAMAI_EDGERC_SECTION")
            else:
                self.section = config.section                    

        except KeyError as k:
            print('\nInput file is missing ' + str(k))    
            exit(-1)
