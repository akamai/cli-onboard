""" Copyright 2019 Akamai Technologies, Inc. All Rights Reserved.
 Licensed under the Apache License, Property 2.0 (the "License");
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

import json
import random
import string

import _logging as lg
from exceptions import setup_logger


logger = setup_logger()
headers = {'Content-Type': 'application/json'}


class apiCallsWrapper:
    def __init__(self, session, access_hostname, account_switch_key):
        self.access_hostname = access_hostname
        self.account_switch_key = f'&accountSwitchKey={account_switch_key}' \
                                  if account_switch_key is not None else ''
        self.session = session

    def formUrl(self, url):
        if '?' in url:
            url = f'{url}{self.account_switch_key}'
        else:
            # Replace & with ? if there is no query string in URL and
            # DO NOT override object property account_switch_key
            upd_acct_switch_key = self.account_switch_key.translate(self.account_switch_key.maketrans('&', '?'))
            url = f'{url}{upd_acct_switch_key}'
        return url

    def property_exists(self, property_name: str):
        url = f'https://{self.access_hostname}/papi/v1/search/find-by-value'
        url = self.formUrl(url)
        payload = {'propertyName': property_name}
        resp = self.session.post(url, headers=headers, json=payload)
        if resp.status_code == 200:
            if len(resp.json()['versions']['items']) == 0:
                return False
            else:
                return True
        return False

    def get_groups_without_parent(self) -> list:
        url = f'https://{self.access_hostname}/papi/v1/groups/'
        url = self.formUrl(url)
        resp = self.session.get(url)

        groups = []
        if resp.status_code == 401:
            lg._log_error('accountSwitchKey is invalid')
        elif resp.status_code == 200:
            for grp in resp.json()['groups']['items']:
                try:
                    if grp['parentGroupId'] is not None:
                        pass
                except KeyError:
                    groups.append(grp)
        return groups

    def checkAuthorization(self):
        """
        Function to check permissions granted for Credentials
        """
        get_credential_details_url = f'https://{self.access_hostname}/-/client-api/active-grants/implicit'
        get_credential_details_url = self.formUrl(get_credential_details_url)

        credential_details_response = self.session.get(get_credential_details_url)
        return credential_details_response

    def createCpcode(self, contractId, groupId, productId, cpcode_name):
        """
        Function to create cpcode
        """
        newCpcodeData = {}
        newCpcodeData['productId'] = f'{productId}'
        newCpcodeData['cpcodeName'] = f'{cpcode_name}'

        create_cpcode_url = f'https://{self.access_hostname}/papi/v1/cpcodes?contractId={contractId}&groupId={groupId}'
        create_cpcode_url = self.formUrl(create_cpcode_url)
        create_cpcode_response = self.session.post(create_cpcode_url,
                                              data=json.dumps(newCpcodeData),
                                              headers=headers)
        return create_cpcode_response

    def createProperty(self, contractId, groupId, productId, property_name):
        """
        Function to create property
        """
        newPropertyData = {}
        newPropertyData['productId'] = f'{productId}'
        newPropertyData['propertyName'] = f'{property_name}'

        create_property_url = f'https://{self.access_hostname}/papi/v1/properties?contractId={contractId}&groupId={groupId}'
        create_property_url = self.formUrl(create_property_url)
        create_property_response = self.session.post(create_property_url,
                                                data=json.dumps(newPropertyData),
                                                headers=headers)
        return create_property_response

    def updatePropertyRules(self, contractId, groupId,
                            propertyId, ruleFormat, ruletree):
        """
        Function to update property rules
        """
        headers = {'Content-Type': 'application/vnd.akamai.papirules.latest+json'}
        if ruleFormat != 'latest':
            version_string = f'application/vnd.akamai.papirules.{ruleFormat}json'
            headers['Content-Type'] = version_string
        update_property_url = 'https://' + self.access_hostname + '/papi/v1/properties/' + \
                              propertyId + '/versions/1/rules?contractId=' + \
                              contractId + '&groupId=' + groupId + '&validateRules=false'
        update_property_url = self.formUrl(update_property_url)
        update_property_response = self.session.put(update_property_url, data=ruletree, headers=headers)
        return update_property_response

    def createEdgehostnameArray(self, hostname_list, edge_hostname_id):
        """
        Function to create Edgehostname array for existing edgehostnames
        """
        edgehostname_list = []
        for eachHostname in hostname_list:
            edgehostnameDetails = {}
            edgehostnameDetails['cnameType'] = 'EDGE_HOSTNAME'
            edgehostnameDetails['edgeHostnameId'] = edge_hostname_id
            edgehostnameDetails['cnameFrom'] = eachHostname
            edgehostname_list.append(edgehostnameDetails)
        return edgehostname_list

    def checkEdgeHostname(self, edge_hostname):
        """
        Function to check the validity of edge_hostname
        """
        dns_zone = ''

        record_name_substring = edge_hostname
        if str(edge_hostname).endswith('edgekey.net'):
            dns_zone = 'edgekey.net'
            record_name_substring = str(edge_hostname).split('.edgekey.net')[0]
        elif str(edge_hostname).endswith('edgesuite.net'):
            dns_zone = 'edgesuite.net'
            record_name_substring = str(edge_hostname).split('.edgesuite.net')[0]
        get_edgehostnameid_url = 'https://' + self.access_hostname + \
                                 '/hapi/v1/edge-hostnames?recordNameSubstring=' + \
                                 record_name_substring + '&dnsZone=' + dns_zone
        get_edgehostnameid_url = self.formUrl(get_edgehostnameid_url)
        edgehostname_response = self.session.get(get_edgehostnameid_url)
        return edgehostname_response

    def updatePropertyHostname(self, contractId, groupId, propertyId, edgehostnamedata):
        """
        Function to update property hostnames and edgehostname
        """
        update_prop_hostname_url = 'https://' + self.access_hostname + \
                                   '/papi/v1/properties/' + propertyId + \
                                   '/versions/1/hostnames?contractId=' + contractId + \
                                   '&groupId=' + groupId + '&validateHostnames=true'
        update_prop_hostname_url = self.formUrl(update_prop_hostname_url)
        update_prop_hostname_response = self.session.put(update_prop_hostname_url,
                                                    data=edgehostnamedata,
                                                    headers=headers)
        return update_prop_hostname_response

    def pollActivationStatus(self, contractId, groupId, propertyId, activationId):
        """
        Function to poll Activation Status
        """
        poll_activation_url = 'https://' + self.access_hostname + \
                              '/papi/v1/properties/' + propertyId + \
                              '/activations/' + activationId + \
                              '?contractId=' + contractId + '&groupId=' + groupId
        poll_activation_url = self.formUrl(poll_activation_url)
        poll_activation_response = self.session.get(poll_activation_url)
        return poll_activation_response

    def activateConfiguration(self, contractId, groupId,
                              propertyId, version: int, network: str,
                              emailList: list, notes: str):
        """
        Function to activate a configuration or property
        """
        activationDetails = {}
        activationDetails['propertyVersion'] = version
        activationDetails['network'] = network
        activationDetails['note'] = notes
        activationDetails['notifyEmails'] = emailList
        complianceRecord = {}
        complianceRecord['noncomplianceReason'] = 'NO_PRODUCTION_TRAFFIC'
        activationDetails['complianceRecord'] = complianceRecord
        logger.debug(json.dumps(activationDetails, indent=4))
        actUrl = 'https://' + self.access_hostname + '/papi/v0/properties/' + propertyId + \
                  '/activations/?contractId=' + contractId + \
                  '&groupId=' + groupId + '&acknowledgeAllWarnings=true'
        actUrl = self.formUrl(actUrl)
        activationResponse = self.session.post(actUrl, data=json.dumps(activationDetails), headers=headers)

        try:
            if activationResponse.status_code == 400 and \
               activationResponse.json()['detail'].find('following activation warnings must be acknowledged'):
                acknowledgeWarnings = []
                for eachWarning in activationResponse.json()['warnings']:
                    # print("WARNING: " + eachWarning['detail'])
                    acknowledgeWarnings.append(eachWarning['messageId'])
                    # acknowledgeWarningsJson = json.dumps(acknowledgeWarnings)
                logger.info('Automatically acknowledging warnings')
                # The details has to be within the three double quote or comment format
                updatedactivationDetails = {}
                updatedactivationDetails['propertyVersion'] = version
                updatedactivationDetails['network'] = f'{network}'
                updatedactivationDetails['note'] = f'{notes}'
                updatedactivationDetails['notifyEmails'] = emailList
                updatedactivationDetails['acknowledgeWarnings'] = acknowledgeWarnings
                complianceRecord = {}
                complianceRecord['noncomplianceReason'] = 'NO_PRODUCTION_TRAFFIC'
                updatedactivationDetails['complianceRecord'] = complianceRecord
                logger.debug(json.dumps(updatedactivationDetails, indent=4))

                updatedactivationResponse = self.session.post(actUrl,
                                                         data=json.dumps(updatedactivationDetails),
                                                         headers=headers)
                if updatedactivationResponse.status_code == 201:
                    logger.debug('Here is the activation link, that can be used to track')
                    logger.debug(updatedactivationResponse.json()['activationLink'])
                    return updatedactivationResponse
                else:
                    return updatedactivationResponse
            elif activationResponse.status_code == 422 and activationResponse.json()['detail'].find('version already activated'):
                logger.info('Property version already activated')
                return activationResponse
            elif activationResponse.status_code == 404 and activationResponse.json()['detail'].find('unable to locate'):
                logger.error('The system was unable to locate the requested version of configuration')
            return activationResponse
        except KeyError:
            logger.error('Looks like there is some error in configuration. Unable to activate configuration at this moment')
            return activationResponse

    def getProductsByContract(self, contractId):
        """
        Function to get product ids for a contract
        """
        get_products_url = f'https://{self.access_hostname}/papi/v1/products?contractId={contractId}'
        get_products_url = self.formUrl(get_products_url)
        get_products_response = self.session.get(get_products_url)
        return get_products_response

    def createEdgehostname(self, productId: str, domainPrefix: str, secureNetwork: str,
                           certEnrollmentId: int,
                           contractId: str, groupId: str):
        """
        Function to Create a edgehostname
        """
        edgehostname_content = {}
        if secureNetwork == 'ENHANCED_TLS':
            edgehostname_content['productId'] = productId
            edgehostname_content['domainPrefix'] = domainPrefix
            edgehostname_content['domainSuffix'] = 'edgekey.net'
            edgehostname_content['secureNetwork'] = secureNetwork
            edgehostname_content['ipVersionBehavior'] = 'IPV4'
            edgehostname_content['certEnrollmentId'] = certEnrollmentId
            logger.warning(f'Trying to create edge_hostname: {domainPrefix}.edgekey.net')
        elif secureNetwork == 'STANDARD_TLS':
            edgehostname_content['productId'] = productId
            edgehostname_content['domainPrefix'] = domainPrefix
            edgehostname_content['domainSuffix'] = 'edgesuite.net'
            edgehostname_content['secureNetwork'] = secureNetwork
            edgehostname_content['ipVersionBehavior'] = 'IPV4'
            logger.warning(f'Trying to create edge_hostname: {domainPrefix}.edgesuite.net')
        else:
            logger.error('Invalid secure network')

        logger.debug(json.dumps(edgehostname_content, indent=4))

        # Create a edgehostname
        create_edgehostname_url = 'https://' + self.access_hostname + \
                                  '/papi/v1/edgehostnames?contractId=' + contractId + \
                                  '&groupId=' + groupId
        create_edgehostname_url = self.formUrl(create_edgehostname_url)
        create_edgehostname_response = self.session.post(create_edgehostname_url,
                                                    data=json.dumps(edgehostname_content),
                                                    headers=headers)

        if create_edgehostname_response.status_code == 201:
            edgehostnameId = create_edgehostname_response.json()['edgeHostnameLink'].split('?')[0].split('/')[4]
            logger.info(f'Successfully created edge_hostname: {edgehostnameId}')
            return edgehostnameId
        else:
            logger.error(json.dumps(create_edgehostname_response.json(), indent=4))
            return -1

    def create_enrollment(self, contractId, data, allowDuplicateCn=True):
        """
        Function to Create an Enrollment

        Parameters
        -----------
        session : <string>
            An EdgeGrid Auth akamai session object

        Returns
        -------
        create_enrollmentRespose : create_enrollmentRespose
            (create_enrollmentRespose) Object with all details
        """
        headers = {
            'Content-Type': 'application/vnd.akamai.cps.enrollment.v4+json',
            'Accept': 'application/vnd.akamai.cps.enrollment-status.v1+json'
        }
        create_enrollment_url = f'https://{self.access_hostname}/cps/v2/enrollments?contractId={contractId}'
        if allowDuplicateCn:
            create_enrollment_url = f'{create_enrollment_url}&allow-duplicate-cn=true'
        create_enrollment_url = self.formUrl(create_enrollment_url)
        create_enrollment_response = self.session.post(create_enrollment_url, data=data, headers=headers)
        return create_enrollment_response

    def getWafConfigurations(self):
        """
        Function to get WAF policy versions
        """
        get_waf_configs_url = f'https://{self.access_hostname}/appsec/v1/configs/'
        get_waf_configs_url = self.formUrl(get_waf_configs_url)
        get_waf_configs_response = self.session.get(get_waf_configs_url)
        return get_waf_configs_response

    def getWafConfigVersions(self, config_id):
        """
        Function to get WAF configs
        """
        get_waf_configversions_url = f'https://{self.access_hostname}/appsec/v1/configs/{config_id}/versions?page=1&pageSize=10&detail=true'
        get_waf_configversions_url = self.formUrl(get_waf_configversions_url)
        waf_configversions_response = self.session.get(get_waf_configversions_url)
        return waf_configversions_response

    def createWafConfigVersion(self, config_id, base_version, notes: str):
        """
        Function to get WAF policy versions
        """
        version_info = {}
        version_info['createFromVersion'] = base_version
        version_info['notes'] = notes
        version_info['ruleUpdate'] = 'false'
        logger.debug(json.dumps(version_info, indent=4))
        create_waf_configversion_url = f'https://{self.access_hostname}/appsec/v1/configs/{config_id}/versions'
        create_waf_configversion_url = self.formUrl(create_waf_configversion_url)
        create_waf_configversion_response = self.session.post(create_waf_configversion_url,
                                                         data=json.dumps(version_info),
                                                         headers=headers)
        logger.debug(create_waf_configversion_response.url)
        return create_waf_configversion_response

    def getMatchTarget(self, config_id, version, target_id):
        """
        Function to get Match Target
        """
        get_match_target_url = f'https://{self.access_hostname}/appsec/v1/configs/{config_id}/versions/{version}/match-targets/{target_id}?includeChildObjectName=true'
        get_match_target_url = self.formUrl(get_match_target_url)
        match_target_response = self.session.get(get_match_target_url)
        return match_target_response

    def list_match_targets(self, config_id, version, policies: dict):
        url = f'https://{self.access_hostname}/appsec/v1/configs/{config_id}/versions/{version}/match-targets'
        url = self.formUrl(url)
        resp = self.session.get(url)
        logger.debug(json.dumps(resp.json()['matchTargets'], indent=3))
        waf_match_target_ids = []
        if resp.status_code == 200:
            web_tgts = resp.json()['matchTargets']['websiteTargets']
            logger.warning(f'{"Policy Name":<20}waf_target_id')
            logger.warning('Website Match Target')
            for tgt in web_tgts:
                policy_id = tgt['securityPolicy']['policyId']
                name = policies[policy_id][0]
                if policy_id in policies.keys():
                    policies[policy_id].append('WEB')
                    policies[policy_id].append(tgt['targetId'])
                waf_match_target_ids.append(tgt['targetId'])
                logger.info(f"{name:20}{tgt['targetId']}")
        else:
            logger.error('The system was unable to locate security match targets.')

        return resp, waf_match_target_ids

    def modifyMatchTarget(self, config_id, version, target_id, data):
        """
        Function to modify Match Target
        """
        match_target_url = f'https://{self.access_hostname}/appsec/v1/configs/{config_id}/versions/{version}/match-targets/{target_id}'
        match_target_url = self.formUrl(match_target_url)
        match_target_response = self.session.put(match_target_url, data=data, headers=headers)
        return match_target_response

    def getWafSelectedHosts(self, config_id, version):
        """
        Function to get Selected Hosts
        """
        get_sel_hosts_url = f'https://{self.access_hostname}/appsec/v1/configs/{config_id}/versions/{version}/selected-hostnames'
        get_sel_hosts_url = self.formUrl(get_sel_hosts_url)
        get_sel_hosts_response = self.session.get(get_sel_hosts_url)
        return get_sel_hosts_response

    def modifyWafHosts(self, config_id, version, data):
        """
        Function to modify/add Hosts
        """
        modify_hosts_url = f'https://{self.access_hostname}/appsec/v1/configs/{config_id}/versions/{version}/selected-hostnames'
        modify_hosts_url = self.formUrl(modify_hosts_url)

        modify_hosts_response = self.session.put(modify_hosts_url, data=data, headers=headers)
        logger.debug(f'{modify_hosts_response.status_code}: {modify_hosts_response.url}')
        logger.debug(data)
        return modify_hosts_response

    def activateWafPolicy(self, config_id: int, version: int,
                          network: str, emails: list, note='Onboard CLI Activation'):
        """
        Function to activate WAF policy version
        """

        data = {}
        data['action'] = 'ACTIVATE'
        data['network'] = network
        data['note'] = note
        data['notificationEmails'] = list(set(emails))  # ensure unique emails

        activationConfigs = {}
        activationConfigs['configId'] = config_id
        activationConfigs['configVersion'] = version
        data['activationConfigs'] = [activationConfigs]
        logger.debug(json.dumps(data, indent=4))

        waf_activate_url = f'https://{self.access_hostname}/appsec/v1/activations'
        waf_activate_url = self.formUrl(waf_activate_url)
        waf_activate_response = self.session.post(waf_activate_url, data=json.dumps(data), headers=headers)
        return waf_activate_response

    def pollWafActivationStatus(self, activationId):
        """
        Function to poll Activation Status
        """
        poll_activation_url = f'https://{self.access_hostname}/appsec/v1/activations/{activationId}'
        poll_activation_url = self.formUrl(poll_activation_url)
        poll_activation_response = self.session.get(poll_activation_url)
        return poll_activation_response

    def valid_hostnames_waf_config(self, ion):
        cid = ion.contract_id[4:]
        gid = ion.group_id[4:]

        url = f'https://{self.access_hostname}/appsec/v1/contracts/{cid}/groups/{gid}/selectable-hostnames'
        url = self.formUrl(url)
        resp = self.session.get(url)
        logger.debug(resp.url)
        return resp

    def create_waf_configurations(self, ion):
        url = self.formUrl(f'https://{self.access_hostname}/appsec/v1/configs')
        logger.debug(ion.public_hostnames)
        payload = {}
        payload['name'] = ion.waf_config_name
        payload['description'] = ''
        payload['hostnames'] = ion.public_hostnames
        payload['contractId'] = ion.contract_id[4:]
        payload['groupId'] = int(ion.group_id[4:])
        logger.debug(payload)

        resp = self.session.post(url, data=json.dumps(payload), headers=headers)
        if resp.status_code == 200 or \
            resp.status_code == 201:
            ion.onboard_waf_config_id = resp.json()['configId']
            ion.onboard_waf_config_version = resp.json()['version']
            self.update_waf_config_version_note(ion, notes=ion.version_notes)
        return resp

    def update_waf_config_version_note(self, ion, notes: str) -> None:
        url = self.formUrl(f'https://{self.access_hostname}/appsec/v1/'
                           f'configs/{ion.onboard_waf_config_id}/'
                           f'versions/{ion.onboard_waf_config_version}/version-notes')
        payload = {}
        payload['notes'] = notes
        resp = self.session.put(url, data=json.dumps(payload), headers=headers)
        logger.debug(resp.status_code)
        logger.debug(resp.url)
        logger.debug(resp.json())

    def create_waf_policy(self, ion):
        url = self.formUrl(f'https://{self.access_hostname}/appsec/v1/configs/{ion.onboard_waf_config_id}/versions/{ion.onboard_waf_config_version}/security-policies')
        payload = {}
        payload['createFromSecurityPolicy'] = ''
        payload['policyName'] = ion.policy_name
        letters = string.ascii_uppercase
        payload['policyPrefix'] = ''.join(random.choice(letters) for i in range(4))
        logger.debug(payload)
        resp = self.session.post(url, data=json.dumps(payload), headers=headers)
        return resp

    def get_waf_policy(self, ion):
        url = self.formUrl(f'https://{self.access_hostname}/appsec/v1/configs/{ion.onboard_waf_config_id}/versions/{ion.onboard_waf_prev_version}/security-policies')
        resp = self.session.get(url, headers=headers)
        policies_name = {}
        if resp.status_code == 200:
            pol_list = resp.json()['policies']
            logger.debug(f'{"Policy Name":<20}Policy ID')

            for p in pol_list:
                logger.debug(f"{p['policyName']:<20}{p['policyId']}")
                policies_name[f"{p['policyId']}"] = [f"{p['policyName']}"]
        return resp, policies_name

    def create_waf_match_target(self, ion):
        url = self.formUrl(f'https://{self.access_hostname}/appsec/v1/configs/{ion.onboard_waf_config_id}/versions/{ion.onboard_waf_config_version}/match-targets')
        payload = {}
        payload['type'] = 'website'
        payload['configId'] = ion.onboard_waf_config_id
        payload['configVersion'] = ion.onboard_waf_config_version
        payload['defaultFile'] = 'NO_MATCH'

        control = {}
        control['applyApplicationLayerControls'] = True
        control['applyNetworkLayerControls'] = True
        control['applyRateControls'] = True
        control['applySlowPostControls'] = True
        payload['effectiveSecurityControls'] = control
        payload['filePaths'] = ['/*']
        payload['hostnames'] = ion.public_hostnames
        payload['isNegativeFileExtensionMatch'] = False
        payload['isNegativePathMatch'] = True

        security = {}
        security['policyId'] = ion.policy_id
        payload['securityPolicy'] = security
        logger.debug(ion)
        logger.debug(payload)
        resp = self.session.post(url, data=json.dumps(payload), headers=headers)
        logger.debug(resp.url)
        return resp
