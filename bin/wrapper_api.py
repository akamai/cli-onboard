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

import json

class apiCallsWrapper(object):
    def __init__(self, access_hostname, account_switch_key):
        self.access_hostname = access_hostname
        if account_switch_key != None:
            self.account_switch_key = '&accountSwitchKey=' + account_switch_key
        else:
            self.account_switch_key = ''

    headers = {
        "Content-Type": "application/json"
    }


    def checkAuthorization(self, session):
        """
        Function to check permissions granted for Credentials
        """
        get_credential_details_url = 'https://' + self.access_hostname + "/-/client-api/active-grants/implicit"

        if '?' in get_credential_details_url:
            get_credential_details_url = get_credential_details_url + self.account_switch_key
        else:
            #Replace & with ? if there is no query string in URL and DO NOT override object property account_switch_key
            account_switch_key = self.account_switch_key.translate(self.account_switch_key.maketrans('&','?'))
            get_credential_details_url = get_credential_details_url + account_switch_key

        credential_details_response = session.get(get_credential_details_url)
        return credential_details_response

    def createCpcode(self,session, contractId, groupId, productId, cpcode_name):
        """
        Function to create cpcode
        """

        newCpcodeData = """
        {
            "productId": "%s",
            "cpcodeName": "%s"
        }
        """ % (productId,cpcode_name)

        create_cpcode_url = 'https://' + self.access_hostname + '/papi/v1/cpcodes?contractId=' + contractId + '&groupId=' + groupId

        if '?' in create_cpcode_url:
            create_cpcode_url = create_cpcode_url + self.account_switch_key
        else:
            #Replace & with ? if there is no query string in URL and DO NOT override object property account_switch_key
            account_switch_key = self.account_switch_key.translate(self.account_switch_key.maketrans('&','?'))
            create_cpcode_url = create_cpcode_url + account_switch_key

        create_cpcode_response = session.post(create_cpcode_url, data=newCpcodeData,headers=self.headers)
        return create_cpcode_response

    def createProperty(self, session, contractId, groupId, productId, property_name):
        """
        Function to create property
        """

        newPropertyData = """
        {
            "productId": "%s",
            "propertyName": "%s"
        }
        """ % (productId,property_name)

        create_property_url = 'https://' + self.access_hostname + '/papi/v1/properties?contractId=' + contractId + '&groupId=' + groupId

        if '?' in create_property_url:
            create_property_url = create_property_url + self.account_switch_key
        else:
            #Replace & with ? if there is no query string in URL and DO NOT override object property account_switch_key
            account_switch_key = self.account_switch_key.translate(self.account_switch_key.maketrans('&','?'))
            create_property_url = create_property_url + account_switch_key

        create_property_response = session.post(create_property_url, data=newPropertyData,headers=self.headers)
        return create_property_response

    def updatePropertyRules(self, session, contractId, groupId, propertyId, ruleFormat, ruletree):
        """
        Function to update property rules
        """

        headers = {
            "Content-Type": "application/vnd.akamai.papirules.latest+json"
        }
        if ruleFormat != 'latest':
            version_string = "application/vnd.akamai.papirules." + str(ruleFormat) + "+json"        
            headers["Content-Type"] = version_string
        
        update_property_url = 'https://' + self.access_hostname + '/papi/v1/properties/' + propertyId +'/versions/1/rules?contractId=' + contractId + '&groupId=' + groupId + '&validateRules=false'

        if '?' in update_property_url:
            update_property_url = update_property_url + self.account_switch_key
        else:
            #Replace & with ? if there is no query string in URL and DO NOT override object property account_switch_key
            account_switch_key = self.account_switch_key.translate(self.account_switch_key.maketrans('&','?'))
            update_property_url = update_property_url + account_switch_key

        update_property_response = session.put(update_property_url, data=ruletree,headers=headers)
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

    def checkEdgeHostname(self, session, edge_hostname):
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

        get_edgehostnameid_url = 'https://' + self.access_hostname + "/hapi/v1/edge-hostnames?recordNameSubstring=" + record_name_substring + '&dnsZone=' + dns_zone

        if '?' in get_edgehostnameid_url:
            get_edgehostnameid_url = get_edgehostnameid_url + self.account_switch_key
        else:
            #Replace & with ? if there is no query string in URL and DO NOT override object property account_switch_key
            account_switch_key = self.account_switch_key.translate(self.account_switch_key.maketrans('&','?'))
            get_edgehostnameid_url = get_edgehostnameid_url + account_switch_key
        edgehostname_response = session.get(get_edgehostnameid_url)
        return edgehostname_response

    def updatePropertyHostname(self, session, contractId, groupId, propertyId, edgehostnamedata):
        """
        Function to update property hostnames and edgehostname
        """
        update_prop_hostname_url = 'https://' + self.access_hostname + '/papi/v1/properties/' + propertyId + '/versions/1/hostnames?contractId=' + contractId + '&groupId=' + groupId + '&validateHostnames=true'

        if '?' in update_prop_hostname_url:
            update_prop_hostname_url = update_prop_hostname_url + self.account_switch_key
        else:
            account_switch_key = self.account_switch_key.translate(self.account_switch_key.maketrans('&','?'))
            update_prop_hostname_url = update_prop_hostname_url + account_switch_key

        update_prop_hostname_response = session.put(update_prop_hostname_url, data=edgehostnamedata, headers=self.headers)
        return update_prop_hostname_response

    def pollActivationStatus(self, session, contractId, groupId, propertyId, activationId):
        """
        Function to poll Activation Status
        """
        poll_activation_url = 'https://' + self.access_hostname + '/papi/v1/properties/' + propertyId + '/activations/' +  activationId + '?contractId=' + contractId + '&groupId=' + groupId

        if '?' in poll_activation_url:
            poll_activation_url = poll_activation_url + self.account_switch_key
        else:
            account_switch_key = self.account_switch_key.translate(self.account_switch_key.maketrans('&','?'))
            poll_activation_url = poll_activation_url + account_switch_key

        poll_activation_response = session.get(poll_activation_url)
        return poll_activation_response

    def activateConfiguration(self, session,propertyName, contractId, groupId, propertyId, version, network, emailList, notes):
        """
        Function to activate a configuration or property
        Parameters
        ----------
        session : <string>
            An EdgeGrid Auth akamai session object
        property_name: <string>
            Property or configuration name
        version : <int>
            version number to be activated
        network : <string>
            network type on which configuration has to be activated on
        emailList : <string>
            List of emailIds separated by comma to be notified
        notes : <string>
            Notes that describes the activation reason
        Returns
        -------
        activationResponse : activationResponse
            (activationResponse) Object with all response details.
        """

        emails = json.dumps(emailList)
        activationDetails = """
             {
                "propertyVersion": %s,
                "network": "%s",
                "note": "%s",
                "notifyEmails": %s,
                "complianceRecord": {
                    "noncomplianceReason": "NO_PRODUCTION_TRAFFIC"
                }
            } """ % (version,network,notes,emails)

        actUrl  = 'https://' + self.access_hostname + '/papi/v0/properties/'+ propertyId + '/activations/?contractId=' + contractId +'&groupId=' + groupId + '&acknowledgeAllWarnings=true'

        if '?' in actUrl:
            actUrl = actUrl + self.account_switch_key
        else:
            account_switch_key = self.account_switch_key.translate(self.account_switch_key.maketrans('&','?'))
            actUrl = actUrl + account_switch_key

        activationResponse = session.post(actUrl, data=activationDetails, headers=self.headers)

        try:
            if activationResponse.status_code == 400 and activationResponse.json()['detail'].find('following activation warnings must be acknowledged'):
                acknowledgeWarnings = []
                for eachWarning in activationResponse.json()['warnings']:
                    #print("WARNING: " + eachWarning['detail'])
                    acknowledgeWarnings.append(eachWarning['messageId'])
                    acknowledgeWarningsJson = json.dumps(acknowledgeWarnings)
                print("Automatically acknowledging warnings")
                #The details has to be within the three double quote or comment format
                updatedactivationDetails = """
                     {
                        "propertyVersion": %s,
                        "network": "%s",
                        "note": "%s",
                        "notifyEmails": %s,
                        "acknowledgeWarnings": %s,
                        "complianceRecord": {
                            "noncomplianceReason": "NO_PRODUCTION_TRAFFIC"
                        }
                    } """ % (version,network,notes,emails,acknowledgeWarningsJson)
                print('Activating property ' + propertyName + ' v1 on ' + network)
                updatedactivationResponse = session.post(actUrl,data=updatedactivationDetails,headers=self.headers)
                if updatedactivationResponse.status_code == 201:
                    #print("Here is the activation link, that can be used to track:\n")
                    #print(updatedactivationResponse.json()['activationLink'])
                    return updatedactivationResponse
                else:
                    return updatedactivationResponse
            elif activationResponse.status_code == 422 and activationResponse.json()['detail'].find('version already activated'):
                print("Property version already activated")
                return activationResponse
            elif activationResponse.status_code == 404 and activationResponse.json()['detail'].find('unable to locate'):
                print("The system was unable to locate the requested version of configuration")
            return activationResponse
        except KeyError:
            print("Looks like there is some error in configuration. Unable to activate configuration at this moment\n")
            return activationResponse

    def getProductsByContract(self, session, contractId):
        """
        Function to get product ids for a contract
        """
        get_products_url = 'https://' + self.access_hostname + '/papi/v1/products?contractId=' + str(contractId)

        if '?' in get_products_url:
            get_products_url = get_products_url + self.account_switch_key
        else:
            #Replace & with ? if there is no query string in URL and DO NOT override object property account_switch_key
            account_switch_key = self.account_switch_key.translate(self.account_switch_key.maketrans('&','?'))
            get_products_url = get_products_url + account_switch_key

        get_products_response = session.get(get_products_url)
        return get_products_response

    def createEdgehostname(self, session, productId, domainPrefix, secureNetwork, certEnrollmentId, slotNumber, contractId, groupId):
        """
        Function to Create a edgehostname
        """
        #Create a edgehostname
        create_edgehostname_url = 'https://' + self.access_hostname + '/papi/v1/edgehostnames?contractId=' + contractId + '&groupId=' + groupId

        if '?' in create_edgehostname_url:
            create_edgehostname_url = create_edgehostname_url + self.account_switch_key
        else:
            account_switch_key = self.account_switch_key.translate(self.account_switch_key.maketrans('&','?'))
            create_edgehostname_url = create_edgehostname_url + account_switch_key

        if secureNetwork == 'ENHANCED_TLS':
            edgehostname_content = """
            {
                "productId": "%s",
                "domainPrefix": "%s",
                "domainSuffix": "edgekey.net",
                "secureNetwork": "%s",
                "ipVersionBehavior": "IPV4",
                "certEnrollmentId": %s,
                "slotNumber": %s
            }""" % (productId, domainPrefix, secureNetwork, certEnrollmentId, slotNumber)
            print('\nTrying to create edge_hostname: ' + domainPrefix + '.edgekey.net')
        elif secureNetwork == 'STANDARD_TLS':
            edgehostname_content = """
            {
                "productId": "%s",
                "domainPrefix": "%s",
                "domainSuffix": "edgesuite.net",
                "secureNetwork": "%s",
                "ipVersionBehavior": "IPV4"
            }""" % (productId, domainPrefix, secureNetwork)
            print('\nTrying to create edge_hostname: ' + domainPrefix + '.edgesuite.net')
        #print(edgehostname_content)

        create_edgehostname_response = session.post(create_edgehostname_url,data=edgehostname_content,headers=self.headers)

        if create_edgehostname_response.status_code == 201:
            edgehostnameId = create_edgehostname_response.json()['edgeHostnameLink'].split('?')[0].split('/')[4]
            print('Successfully created edge_hostname: ' + str(edgehostnameId))
            return edgehostnameId
        else:
            print(json.dumps(create_edgehostname_response.json(), indent=4))
            return -1


    def create_enrollment(self, session, contractId, data, allowDuplicateCn=True):
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
            "Content-Type": "application/vnd.akamai.cps.enrollment.v4+json",
            "Accept": "application/vnd.akamai.cps.enrollment-status.v1+json"
        }
        create_enrollment_url = 'https://' + self.access_hostname + \
            '/cps/v2/enrollments?contractId=' + contractId
        if allowDuplicateCn:
            create_enrollment_url = create_enrollment_url + '&allow-duplicate-cn=true'
        if '?' in create_enrollment_url:
            create_enrollment_url = create_enrollment_url + self.account_switch_key
        else:
            #Replace & with ? if there is no query string in URL
            self.account_switch_key = self.account_switch_key.translate(self.account_switch_key.maketrans('&','?'))
            create_enrollment_url = create_enrollment_url + self.account_switch_key

        create_enrollment_response = session.post(create_enrollment_url, data=data, headers=headers)
        return create_enrollment_response

    def getWafConfigurations(self, session):
        """
        Function to get WAF policy versions
        """

        get_waf_configs_url = 'https://' + self.access_hostname + '/appsec/v1/configs/'

        if '?' in get_waf_configs_url:
            get_waf_configs_url = get_waf_configs_url + self.account_switch_key
        else:
            #Replace & with ? if there is no query string in URL and DO NOT override object property account_switch_key
            account_switch_key = self.account_switch_key.translate(self.account_switch_key.maketrans('&','?'))
            get_waf_configs_url = get_waf_configs_url + account_switch_key

        get_waf_configs_response = session.get(get_waf_configs_url)
        return get_waf_configs_response

    def getWafConfigVersions(self, session, config_id):
        """
        Function to get WAF configs
        """

        get_waf_configversions_url = 'https://' + self.access_hostname + '/appsec/v1/configs/' + str(config_id) + '/versions?page=1&pageSize=10&detail=true'

        if '?' in get_waf_configversions_url:
            get_waf_configversions_url = get_waf_configversions_url + self.account_switch_key
        else:
            #Replace & with ? if there is no query string in URL and DO NOT override object property account_switch_key
            account_switch_key = self.account_switch_key.translate(self.account_switch_key.maketrans('&','?'))
            get_waf_configversions_url = get_waf_configversions_url + account_switch_key

        waf_configversions_response = session.get(get_waf_configversions_url)
        return waf_configversions_response

    def createWafConfigVersion(self, session, config_id, base_version):
        """
        Function to get WAF policy versions
        """

        create_waf_configversion_url = 'https://' + self.access_hostname + '/appsec/v1/configs/' + str(config_id) + '/versions'

        if '?' in create_waf_configversion_url:
            create_waf_configversion_url = create_waf_configversion_url + self.account_switch_key
        else:
            #Replace & with ? if there is no query string in URL and DO NOT override object property account_switch_key
            account_switch_key = self.account_switch_key.translate(self.account_switch_key.maketrans('&','?'))
            create_waf_configversion_url = create_waf_configversion_url + account_switch_key

        version_info = """
        {
            "createFromVersion": %s,
            "ruleUpdate": false
        }""" % (base_version)

        create_waf_configversion_response = session.post(create_waf_configversion_url,data=version_info,headers=self.headers)
        return create_waf_configversion_response

    def getMatchTarget(self, session, config_id, version, target_id):
        """
        Function to get Match Target
        """

        get_match_target_url = 'https://' + self.access_hostname + '/appsec/v1/configs/' + str(config_id) + '/versions/' + str(version) + '/match-targets/' + str(target_id) + '?includeChildObjectName=true'

        if '?' in get_match_target_url:
            get_match_target_url = get_match_target_url + self.account_switch_key
        else:
            #Replace & with ? if there is no query string in URL and DO NOT override object property account_switch_key
            account_switch_key = self.account_switch_key.translate(self.account_switch_key.maketrans('&','?'))
            get_match_target_url = get_match_target_url + account_switch_key

        match_target_response = session.get(get_match_target_url)
        return match_target_response

    def modifyMatchTarget(self, session, config_id, version, target_id, data):
        """
        Function to modify Match Target
        """

        match_target_url = 'https://' + self.access_hostname + '/appsec/v1/configs/' + str(config_id) + '/versions/' + str(version) + '/match-targets/' + str(target_id)

        if '?' in match_target_url:
            match_target_url = match_target_url + self.account_switch_key
        else:
            #Replace & with ? if there is no query string in URL and DO NOT override object property account_switch_key
            account_switch_key = self.account_switch_key.translate(self.account_switch_key.maketrans('&','?'))
            match_target_url = match_target_url + account_switch_key

        match_target_response = session.put(match_target_url,data=data,headers=self.headers)
        return match_target_response

    def getWafSelectedHosts(self, session, config_id, version):
        """
        Function to get Selected Hosts
        """

        get_sel_hosts_url = 'https://' + self.access_hostname + '/appsec/v1/configs/' + str(config_id) + '/versions/' + str(version) + '/selected-hostnames'

        if '?' in get_sel_hosts_url:
            get_sel_hosts_url = get_sel_hosts_url + self.account_switch_key
        else:
            #Replace & with ? if there is no query string in URL and DO NOT override object property account_switch_key
            account_switch_key = self.account_switch_key.translate(self.account_switch_key.maketrans('&','?'))
            get_sel_hosts_url = get_sel_hosts_url + account_switch_key

        get_sel_hosts_response = session.get(get_sel_hosts_url)
        return get_sel_hosts_response

    def modifyWafHosts(self, session, config_id, version, data):
        """
        Function to modify/add Hosts
        """

        modify_hosts_url = 'https://' + self.access_hostname + '/appsec/v1/configs/' + str(config_id) + '/versions/' + str(version) + '/selected-hostnames'

        if '?' in modify_hosts_url:
            modify_hosts_url = modify_hosts_url + self.account_switch_key
        else:
            #Replace & with ? if there is no query string in URL and DO NOT override object property account_switch_key
            account_switch_key = self.account_switch_key.translate(self.account_switch_key.maketrans('&','?'))
            modify_hosts_url = modify_hosts_url + account_switch_key

        modify_hosts_response = session.put(modify_hosts_url,data=data,headers=self.headers)
        return modify_hosts_response

    def activateWafPolicy(self, session, config_id, version, network, emails,note="Onboard CLI Activation"):
        """
        Function to activate WAF policy version
        """

        waf_activate_url = 'https://' + self.access_hostname + '/appsec/v1/activations'

        if '?' in waf_activate_url:
            waf_activate_url = waf_activate_url + self.account_switch_key
        else:
            #Replace & with ? if there is no query string in URL and DO NOT override object property account_switch_key
            account_switch_key = self.account_switch_key.translate(self.account_switch_key.maketrans('&','?'))
            waf_activate_url = waf_activate_url + account_switch_key

        emailList = json.dumps(emails)
        data = """
        {
            "action": "ACTIVATE",
            "network": "%s",
            "note": "%s",
            "notificationEmails": %s,
            "activationConfigs": [
                {
                    "configId": %s,
                    "configVersion": %s
                }
            ]
        }""" % (network, note, emailList, config_id, version)

        waf_activate_response = session.post(waf_activate_url,data=data,headers=self.headers)
        return waf_activate_response

    def pollWafActivationStatus(self, session, contractId, groupId, propertyId, activationId):
        """
        Function to poll Activation Status
        """
        poll_activation_url = 'https://' + self.access_hostname + '/appsec/v1/activations/' + str(activationId)

        if '?' in poll_activation_url:
            poll_activation_url = poll_activation_url + self.account_switch_key
        else:
            account_switch_key = self.account_switch_key.translate(self.account_switch_key.maketrans('&','?'))
            poll_activation_url = poll_activation_url + account_switch_key

        poll_activation_response = session.get(poll_activation_url)
        return poll_activation_response
