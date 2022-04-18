import json
import subprocess
import time
from time import strftime
from time import gmtime
import os
import shutil

class papiFunctions(object):
    def activateAndPoll(self, session, wrapper_object, property_name, contract_id, group_id, property_id, version, network, emailList, notes):
        """
        Function to activate a property to Akamai Staging or Production network.
        """
        print('\nPreparing to activate property to Akamai ' + network + ' network')
        start_time = round(time.time())
        act_response = wrapper_object.activateConfiguration(session, property_name, \
                    contract_id, group_id, property_id, version, network, emailList, notes)
        if act_response.status_code == 201:
            activation_status = False
            activation_id = act_response.json()['activationLink'].split('?')[0].split('/')[-1]
            while activation_status is False:
                print('Polling 30s...')
                activation_status_response = wrapper_object.pollActivationStatus(session, contract_id, group_id, property_id, activation_id)
                if activation_status_response.status_code == 200:
                    for each_activation in activation_status_response.json()['activations']['items']:
                        if each_activation['activationId'] == activation_id:
                            if network in each_activation['network']:
                                if each_activation['status'] != 'ACTIVE':
                                    time.sleep(30)
                                elif each_activation['status'] == 'ACTIVE':
                                    end_time = round(time.time())
                                    command_time = end_time - start_time
                                    print('Duration: ' + str(strftime("%H:%M:%S", gmtime(command_time))))
                                    print('Successfully activated property to Akamai ' + network + ' network')
                                    activation_status = True
                                    return activation_status
                                else:
                                    print('ERROR: Unable to parse activation status')
                                    activation_status = False
                                    return activation_status
                else:
                    print(json.dumps(activation_status_response.json(), indent=4))
                    print('ERROR: Unable to get activation status')
                    return False
        else:
            print(json.dumps(act_response.json(), indent=4))
            return False

    def createNewCpCode(self, session, onboard_object, wrapper_object, cpcode_name, contract_id, group_id, product_id):
        """
        Function to create new cpcode
        """
        create_cpcode_response = wrapper_object.createCpcode(session, contract_id, group_id, product_id, cpcode_name)

        if create_cpcode_response.status_code == 201:
            new_cpcode = create_cpcode_response.json()['cpcodeLink'].split('?')[0].split('/')[-1].replace('cpc_','')
            onboard_object.onboard_default_cpcode = int(new_cpcode)
            print('Successfully created new cpcode: ' + str(new_cpcode))
        else:
            print(json.dumps(create_cpcode_response.json(), indent=4))
            print('\nERROR: Unable to create new cpcode')
            exit(-1)

    def createAndUpdateProperty(self, session, setup_json_content, onboard_object, wrapper_object, utility_object):
        """
        Function with multiple goals:
            1. Create a property
            2. Update the property with template rules define
        """
        print('Trying to create property: ' + onboard_object.property_name)
        create_property_response = wrapper_object.createProperty(session, onboard_object.contract_id, \
                                                                onboard_object.group_id, \
                                                                onboard_object.product_id, \
                                                                onboard_object.property_name)
        if create_property_response.status_code == 201:
            onboard_object.onboard_property_id = create_property_response.json()['propertyLink'].split('?')[0].split('/')[-1]
            print('Successfully created property: ' + onboard_object.onboard_property_id)
        else:
            print(json.dumps(create_property_response.json(), indent=4))
            print('\nERROR: Unable to create property')
            exit(-1)

        #Do edgehostname logic
        edgeHostname_id = self.processEdgeHostnameInput(session, onboard_object, wrapper_object, utility_object, setup_json_content)
        if edgeHostname_id != -1:
            edgehostname_list = wrapper_object.createEdgehostnameArray(onboard_object.public_hostnames, edgeHostname_id)
        else:
            print('\nERROR: Unable to proceed beyond edge hostname and/or ssl certificate logic')
            exit(-1)


        #Update property hostnames and edgehostnames
        print('\nTrying to update property public_hostnames and edge_hostname')
        property_update_reponse = wrapper_object.updatePropertyHostname(session, onboard_object.contract_id, \
                                                                        onboard_object.group_id, \
                                                                        onboard_object.onboard_property_id, \
                                                                        json.dumps(edgehostname_list))
        if property_update_reponse.status_code == 200:
            print('Successfully updated property public_hostnames and edge_hostname')
        else:
            print('\nERROR: Unable to update property public_hostnames and edge_hostname')
            print(json.dumps(property_update_reponse.json(), indent=4))
            exit(-1)

        if(onboard_object.use_file):

            #Do Akamai pipeline merge from file
            print('\nTrying to create property rules json from merging files specified in file_info')
            if(utility_object.doCliPipelineMerge(onboard_object, create_mode=True, merge_type="pm")):
                print('Successfully merged variables and values from file_info')

                #Update property with value substituted json
                with open(os.path.join('temp_pm','dist','test.temp_pm.papi.json'),'r') as updateTemplateFile:
                    updateContent = json.load(updateTemplateFile)

            else:
                print('\nERROR: Unable to merge variables and values from file_info. Please check temp_pm folder to see if merge output file was created in dist folder and/or devops-log.log for more details')
                exit(-1)
        elif(onboard_object.use_folder):
            #Do Akamai pipeline merge from folder path
            print('\nTrying to create property rules json from merging files specified in folder_info')
            if(utility_object.doCliPipelineMerge(onboard_object, create_mode=False, merge_type="pm")):
                print('Successfully merged variables and values from folder_info')

                #Update property with value substituted json
                with open(os.path.join('temp_pm','dist',onboard_object.env_name + '.temp_pm.papi.json'),'r') as updateTemplateFile:
                    updateContent = json.load(updateTemplateFile)
            else:
                print('\nERROR: Unable to merge variables and values from folder_info. Please check temp_pm folder to see if merge output file was created in dist folder and/or devops-log.log for more details')
                exit(-1)

        #Update the json data to include is_secure if its a secure network enabled config
        #Values have already been validated
        if onboard_object.secure_network == 'ENHANCED_TLS':
            updateContent['options'] = dict()
            updateContent['options']['is_secure'] = True
        else:
            #This is a non-secure configuration
            updateContent['options'] = dict()
            updateContent['options']['is_secure'] = False
        updateContent['comments'] = 'Created using Onboard CLI'
        updateContent['ruleFormat'] = onboard_object.rule_format


        #Update default rule cpcode if necessary (should have already been created by this step)
        if onboard_object.onboard_default_cpcode > 0:
            try:
                #look for the cpcode behavior in the default rule and update it
                for each_behavior in updateContent['rules']['behaviors']:
                    if each_behavior['name'] == 'cpCode':
                        each_behavior['options']['value']['id'] = int(onboard_object.onboard_default_cpcode)
                        print('Updated default rule with with cpcode: ' + str(onboard_object.onboard_default_cpcode))
                        break
            except:
                #cp code behavior didn't exist in default rule for some reason so must be error with template and error
                print('\nERROR: Unable to update default rule cpcode')
                exit(-1)

        #Update Property Rules
        updateRulesResponse = wrapper_object.updatePropertyRules(session, onboard_object.contract_id, \
                                                                          onboard_object.group_id, \
                                                                          onboard_object.onboard_property_id, \
                                                                          onboard_object.rule_format, \
                                                                          ruletree=json.dumps(updateContent))



        if updateRulesResponse.status_code == 200:
            print('\nSuccessfully updated property with rules')
        else:
            print(json.dumps(updateRulesResponse.json(), indent=4))
            print('\nERROR: Unable to update rules for property')
            exit(-1)

        #Step 7: Delete the temporary pipeline directory structure for property manager merge
        if os.path.exists('temp_pm'):
            shutil.rmtree('temp_pm')
            try:
                os.remove('devops.log')
            except:
                pass    

            try:
                os.remove('devops-logs.log')    
            except:
                pass 

    def processEdgeHostnameInput(self, session, onboard_object, wrapper_object, utility_object, setup_json_content):
        """
        Function to determine steps on edgehostname and return edge hostname id that will be used in the new onboarded property
        Return edge hostname id should start with ehn_ because that's what subsequent apis calls need
        By time this method is called, onboard_object should already have edge_hostname_id set by validate steps up front
        """
        print('\nEdge Hostname Mode: ' + onboard_object.edge_hostname_mode)
        if onboard_object.edge_hostname_mode == 'use_existing_edgehostname':
            edgeHostnameId = 'ehn_' + str(onboard_object.edge_hostname_id)
            return edgeHostnameId
        elif onboard_object.edge_hostname_mode == 'new_standard_tls_edgehostname':
            product_id = onboard_object.product_id
            domain_prefix = onboard_object.public_hostnames[0]
            edgehostname_id = wrapper_object.createEdgehostname(session, \
                                                                onboard_object.product_id, \
                                                                onboard_object.public_hostnames[0], \
                                                                onboard_object.secure_network, \
                                                                '', \
                                                                '', \
                                                                onboard_object.contract_id, \
                                                                onboard_object.group_id)
            #Response will be either the edgeHostnameId of -1 in case of failure
            return edgehostname_id
        elif onboard_object.edge_hostname_mode == 'new_enhanced_tls_edgehostname':
            if onboard_object.use_existing_enrollment_id is True:
                product_id = onboard_object.product_id
                domain_prefix = onboard_object.public_hostnames[0]
                edgehostname_id = wrapper_object.createEdgehostname(session, \
                                                                    onboard_object.product_id, \
                                                                    onboard_object.public_hostnames[0], \
                                                                    onboard_object.secure_network, \
                                                                    onboard_object.existing_enrollment_id, \
                                                                    onboard_object.existing_slot_number, \
                                                                    onboard_object.contract_id, \
                                                                    onboard_object.group_id)
                #Response will be either the edgeHostnameId of -1 in case of failure
                return edgehostname_id
            elif onboard_object.create_new_ssl_cert is True:
                            
                #Invoke merge
                print('\nTrying to create ssl cert json from merging files specified in ssl_cert_info')
                if(utility_object.doCliPipelineMerge(onboard_object, create_mode=True, merge_type="cps")):
                    print('Successfully merged variables and values from ssl_cert_info')

                    #Read the certificate data file, created from merge
                    with open(os.path.join('temp_cps','dist','test.temp_cps.papi.json'), mode='r') as inputFileHandler:
                        file_content = inputFileHandler.read()
                else:
                    print('\nERROR: Unable to merge variables and values from ssl_cert_info. Please check temp_cps folder to see if merge output file was created in dist folder and/or devops-log.log for more details')
                    exit(-1)                    

                json_formatted_content = json.loads(file_content)
                updated_json_content = json.dumps(json_formatted_content, indent=2)

                print('\nTrying to create a new certificate enrollment')
                if onboard_object.contract_id.startswith('ctr_'):
                    contract_id = onboard_object.contract_id.split('_')[1]
                else:
                    contract_id = onboard_object.contract_id
                create_enrollment_response = wrapper_object.create_enrollment(session, contract_id, data=updated_json_content, allowDuplicateCn=False)
                if create_enrollment_response.status_code != 200 and create_enrollment_response.status_code != 202:
                    print(create_enrollment_response.text)
                    print('\nERROR: Unable to create certificate enrollment')
                    return -1
                else:
                    print('Successfully created certificate enrollment')

                    #Delete the pipeline temporary directory used for cps merge only after certificate enrollment is successfully created.
                    #If we didn't get here, leave the temp_cps folder the so user can debug
                    if os.path.exists('temp_cps'):
                        shutil.rmtree('temp_cps')
                        try:
                            os.remove('devops.log')
                        except:
                            pass    

                        try:
                            os.remove('devops-logs.log')    
                        except:
                            pass 
            
                    if onboard_object.temp_existing_edge_hostname != "":
                        print('\nNOTE: New edge hostname cannot be created yet from this new certificate.  Please create edge hostname after certificate has been deployed. Associating specified temp_edge_hostname to property for now.')
                        edgehostname_id = 'ehn_' + str(onboard_object.edge_hostname_id)
                        return edgehostname_id
                    else:
                        #This block should never get executed because up front validation requires temp edge_hostname to be used if create_new_ssl_cert
                        #Akamai APIs do not allow you to create edge hostname right way based of the new enrollment that was created. There is some delay
                        #But in the future if Akamai APIs allow you to create new edge hostname right away after new enrollment created, hopefully should not need
                        #temp edge hostname workaround
                        domain_prefix = onboard_object.public_hostnames[0]
                        cert_enrollment_id = create_enrollment_response.json()['enrollment'].split('/')[-1]

                        #Create edgehostname
                        edgehostname_id = wrapper_object.createEdgehostname(session, \
                                                                            onboard_object.product_id, \
                                                                            domain_prefix, \
                                                                            onboard_object.secure_network, \
                                                                            cert_enrollment_id, \
                                                                            '', \
                                                                            onboard_object.contract_id, \
                                                                            onboard_object.group_id)

                        #Response will be either the edgeHostnameId of -1 in case of failure
                        return edgehostname_id
        else:
            print('ERROR: Unknown edge_hostname_mode: ' + str(onboard_object.edge_hostname_mode))
            return(-1)
