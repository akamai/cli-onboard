from shutil import which
import subprocess
import json
from urllib import parse
import os
from distutils.dir_util import copy_tree
import shutil
import os

class utility(object):
    def __init__(self):
        """
        Function to initialize a common status indicator,
        This variable should be updated by every function
        defined in validation modules to indicate validation status.
        This avoid usage of too many IF Conditions.
        """
        #Initialize the variable to true
        self.valid = True

    def installedCommandCheck(self, command_name):
        """
        Function to check installation of a command.
        """
        if which(command_name) is None:
            #This is a failure state, if the command is installed
            print('\nThis program needs ' + command_name + ' as a pre-requisite')
            if command_name == 'akamai':
                print('Please install from https://github.com/akamai/cli')
            else:
                #Default print statement
                print('\n' + command_name + ' is not installed')

            #Common assignment for Failure cases
            self.valid = False
            exit(-1)
            return self.valid
        else:
            #This is a success state, if the command is installed
            return self.valid

        #Default Return, ideally code shouldnt come here
        return self.valid

    def executeCommand(self, command):
        """
        Function to execute Linux commands
        """
        childprocess = subprocess.Popen(command, 
                    stdout=subprocess.PIPE, 
                    stderr=subprocess.STDOUT)
        stdout,stderr = childprocess.communicate()    

        if 'pipeline' in command:
            if 'akamai [global flags]' in str(stdout):
                #Check specifically for akamai pipeline
                print('\nThis program needs akamai CLI module property-manager as a pre-requisite')
                print('Please install from https://github.com/akamai/cli-property-manager')

                #Common assignment for Failure cases
                self.valid = False
                exit(-1)
                return self.valid
            else:
                return self.valid                                       

        #Default Return, ideally code shouldnt come here
        return self.valid   


    def checkPermissions(self, session, apicalls_wrapper_object):
        """
        Function to check credentials permissions required
        """
        #This function is not used. Helpful in future if we want to check permissions of credential
        credential_details_response = apicalls_wrapper_object.checkAuthorization(session)
        print(json.dumps(credential_details_response.json(), indent=4))
        if credential_details_response.status_code == 200:
        	for scope in credential_details_response.json()['scope'].split(" "):
        		o = parse.urlparse(scope)
        		apis = o.path.split("/")
        		print('{0:35} {1:10}'.format(apis[3], apis[5]))
        else:
            pass
        #Default Return, ideally code shouldnt come here
        return self.valid

    def validateSetupSteps(self, session, onboard_object, wrapper_object):
        """
        Function to validate the input values of setup.json
        """
        if onboard_object.secure_network != 'ENHANCED_TLS' and onboard_object.secure_network != 'STANDARD_TLS':
            print('ERROR: secure_network must be either ENHANCED_TLS or STANDARD_TLS')
            self.valid = False
            return False
        
        if onboard_object.use_file is True and onboard_object.use_folder is True:
            print('ERROR: Both use_file and use_folder cannot be set to true')
            self.valid = False
            return False

        if onboard_object.use_file is not True and onboard_object.use_folder is not True:
            print('ERROR: Either use_file or use_folder must be set to true')
            self.valid = False
            return False

        if onboard_object.create_new_cpcode is True:
            if onboard_object.new_cpcode_name == "":
                print('ERROR: If create_new_cpcode is true, new_cpcode_name must be specified')
                self.valid = False

        if onboard_object.use_file is True:
            if onboard_object.source_template_file == "":
                print('ERROR: If use_file is true, source_template_file must be specified')
                self.valid = False
            if onboard_object.source_values_file == "":
                print('ERROR: If use_file is true, source_values_file must be specified')
                self.valid = False


        if onboard_object.use_folder is True:
            if onboard_object.folder_path == "":
                print('ERROR: If use_folder is true, folder_path must be specified')
                self.valid = False
            if onboard_object.env_name == "":
                print('ERROR: If use_folder is true, env_name must be specified')
                self.valid = False


        if onboard_object.activate_property_production is True:
            if onboard_object.activate_property_staging is not True:
                print('ERROR: Must activate property to STAGING before activating to PRODUCTION')
                self.valid = False
            else:
                pass


        if onboard_object.add_selected_host is True:
            if onboard_object.activate_property_staging is not True:
                print('ERROR: If adding WAF selected hosts, property must be activated to STAGING')
                self.valid = False
            else:
                pass

        if onboard_object.update_match_target is True:
            if onboard_object.activate_property_staging is not True:
                print('ERROR: If adding WAF match target, property must be activated to STAGING')
                self.valid = False
            else:
                pass

        if onboard_object.update_match_target is True:
            if onboard_object.add_selected_host is not True:
                print('ERROR: If adding WAF match target, must be added to WAF selected hosts')
                self.valid = False
            else:
                pass

        if onboard_object.activate_waf_policy_staging is True:
            if onboard_object.add_selected_host is not True:
                print('ERROR: If activating WAF policy to STAGING, must at least add WAF selected hosts')
                self.valid = False
            else:
                pass

        if onboard_object.activate_waf_policy_production is True:
            if onboard_object.activate_waf_policy_staging is not True:
                print('ERROR: Must activate WAF policy to STAGING before activating to PRODUCTION.')
                self.valid = False
            else:
                pass

        #Check if product_id is valid for contract
        print('Checking if valid product_id: ' + onboard_object.product_id)
        product_detail = self.validateProductId(session, wrapper_object, onboard_object.contract_id, onboard_object.product_id)
        if product_detail['Found'] is True:
            print('Confirmed valid product_id')
        else:
            print('ERROR: Invalid product_id for contract: ' + onboard_object.contract_id)
            print('ERROR: Please select from valid product_ids for this contract: ' + str(product_detail['products']))
            self.valid = False


        if onboard_object.edge_hostname_mode == 'use_existing_edgehostname':
            if self.valid:
                print('\nedge_hostname_mode = use_existing_edgehostname\n')
            if onboard_object.edge_hostname == "":
                    print('ERROR: If use_existing_edgehostname, edge_hostname is mandatory')
                    self.valid = False
            else:
                if onboard_object.secure_network == 'ENHANCED_TLS':
                    if not str(onboard_object.edge_hostname).endswith('edgekey.net'):
                        print('ERROR: If secure_network is ENHANCED_TLS, existing edge_hostname must end with edgekey.net')
                        self.valid = False
                        return False
                elif onboard_object.secure_network == 'STANDARD_TLS':    
                    if not str(onboard_object.edge_hostname).endswith('edgesuite.net'):
                        print('ERROR: If secure_network is STANDARD_TLS, existing edge_hostname must end with edgesuite.net')
                        self.valid = False
                        return False

            #Validate edgehostname and validate the necessary
            if self.valid:
                #Check the validity of edgehostname
                print('Checking if valid edge_hostname: ' + str(onboard_object.edge_hostname))
                ehn_id = self.validateEdgeHostnameExists(session, wrapper_object, str(onboard_object.edge_hostname))
                if ehn_id > 0:
                    print('Confirmed valid edge_hostname: ehn_' + str(ehn_id))
                    onboard_object.edge_hostname_id = ehn_id
                else:
                    print('ERROR: edge_hostname is not found')
                    self.valid = False

        if onboard_object.edge_hostname_mode == 'new_standard_tls_edgehostname':
            print('\nedge_hostname_mode = new_standard_tls_edgehostname\n')
            if onboard_object.secure_network != 'STANDARD_TLS':    
                print('ERROR: For new_standard_tls_edgehostname, secure_network must be STANDARD_TLS')
                self.valid = False
                return False                    

        if onboard_object.edge_hostname_mode == 'new_enhanced_tls_edgehostname':
            print('\nedge_hostname_mode = new_enhanced_tls_edgehostname\n')
            if onboard_object.secure_network != 'ENHANCED_TLS':    
                print('ERROR: For new_enhanced_tls_edgehostname, secure_network must be ENHANCED_TLS')
                self.valid = False
                return False                    
            
            if onboard_object.use_existing_enrollment_id is True:
                if onboard_object.create_new_ssl_cert is True:
                    print('ERROR: Both use_existing_enrollment_id and create_new_ssl_cert cannot be set to true')
                    self.valid = False
                if onboard_object.existing_enrollment_id == "":
                    print('ERROR: If use_existing_enrollment_id is true, existing_enrollment_id is mandatory')
                    self.valid = False
                if onboard_object.existing_slot_number == "":
                    print('ERROR: If use_existing_enrollment_id is true, existing_slot_number is mandatory')
                    self.valid = False
            elif onboard_object.create_new_ssl_cert is True:
                if onboard_object.temp_existing_edge_hostname == "":
                    print('ERROR: If create_new_ssl_cert is true, temp_existing_edge_hostname must be specified')
                    self.valid = False
                else:
                    if onboard_object.secure_network == 'ENHANCED_TLS':
                        if not str(onboard_object.temp_existing_edge_hostname).endswith('edgekey.net'):
                            print('ERROR: If secure_network is ENHANCED_TLS, temp_existing_edge_hostname must end with edgekey.net')
                            self.valid = False
                            return False
                if onboard_object.ssl_cert_template_file is None or onboard_object.ssl_cert_template_values is None:
                    print('ERROR: If create_new_ssl_cert is true, ssl_cert_template_file and ssl_cert_template_values must be specified')
                    self.valid = False
                if self.validateFile(onboard_object.ssl_cert_template_file):
                    if self.validateFile(onboard_object.ssl_cert_template_values):
                        pass
                    else:
                        #File does not exist
                        print('ERROR: ' + onboard_object.ssl_cert_template_values + ' does not exist')
                        self.valid = False
                else:
                    #File does not exist
                    print('ERROR: ' + onboard_object.ssl_cert_template_file + ' does not exist')
                    self.valid = False

                #Validate the temp_existing_edge_hostname
                if self.valid:
                    print('Checking if valid temp_existing_edge_hostname: ' + str(onboard_object.temp_existing_edge_hostname))
                    ehn_id = self.validateEdgeHostnameExists(session, wrapper_object, str(onboard_object.temp_existing_edge_hostname))
                    if ehn_id > 0:
                        print('Confirmed valid temp_existing_edge_hostname: ehn_' + str(ehn_id))
                        onboard_object.edge_hostname_id = ehn_id
                    else:
                        print('ERROR: temp_existing_edge_hostname is not found')
                        self.valid = False


        if onboard_object.use_file is True:
            if self.validateFile(onboard_object.source_template_file):
                if self.validateFile(onboard_object.source_values_file):
                    pass
                else:
                    #File does not exist
                    print('ERROR: ' + onboard_object.source_values_file + ' does not exist')
                    self.valid = False
            else:
                #File does not exist
                print('ERROR: ' + onboard_object.source_template_file + ' does not exist')
                self.valid = False
        
        #If supposed to something with WAF, can we find waf_config_id for the specifed name
        if onboard_object.add_selected_host is True:
            print('\nChecking if valid waf_config_name: ' + onboard_object.waf_config_name)
            config_detail = self.getWafConfigIdByName(session, wrapper_object,onboard_object.waf_config_name)
            if config_detail['Found'] is True:
                onboard_object.onboard_waf_config_id = config_detail['details']['id']
                print('Found valid waf_config_id: ' + str(onboard_object.onboard_waf_config_id))

                onboard_object.onboard_waf_prev_version = config_detail['details']['latestVersion']
            else:
                print('ERROR: Unable to find valid waf configuration for waf_config_name: ' + onboard_object.waf_config_name)
                self.valid = False

        #Default Return, only use this return as every settings needs to be checked
        return self.valid

    #Validate file
    def validateFile(self, file_location):
        if os.path.isfile(file_location):
            return True
        else:
            return False

    def validateProductId(self, session, wrapper_object, contract_id, product_id):
        """
        Function to validate product ids for a contract
        """
        
        products = dict()
        products['Found'] = False
        products['products'] = []
        get_products_response = wrapper_object.getProductsByContract(session, contract_id)
        if get_products_response.status_code == 200:
            items = get_products_response.json()['products']['items']
            for each_item in items:
                if 'productId' in each_item:
                    if each_item['productId'].lower() == product_id.lower():
                        products['Found'] = True
                    products['products'].append(each_item['productId'])
                else:
                    pass
        else:
            print(json.dumps(get_products_response.json(), indent=4))
            pass

        return products    

    def validateEdgeHostnameExists(self, session, wrapper_object, edge_hostname):
        """
        Function to validate edge hostname
        """

        ehn_id = 0
        edgehostname_response = wrapper_object.checkEdgeHostname(session, edge_hostname)
        record_name = edge_hostname
        if str(edge_hostname).endswith('edgekey.net'):
            record_name = str(edge_hostname).split('.edgekey.net')[0]
        elif str(edge_hostname).endswith('edgesuite.net'):
            record_name = str(edge_hostname).split('.edgesuite.net')[0]  

        if edgehostname_response.status_code == 200:
            ehns = edgehostname_response.json()['edgeHostnames']
            for every_ehn in ehns:
                if every_ehn['recordName'] == record_name:
                    ehn_id = every_ehn['edgeHostnameId']
                    return ehn_id
                else:
                    pass    
        else:
            print(json.dumps(edgehostname_response.json(), indent=4))
            return 0

        return ehn_id 

    def getWafConfigIdByName(self, session, wrapper_object, config_name):
        """
        Function to get WAF config ID and version
        """
        config_detail = dict()
        config_detail['Found'] = False
        waf_configs_response = wrapper_object.getWafConfigurations(session)
        if waf_configs_response.status_code == 200:
            configurations = waf_configs_response.json()['configurations']
            for each_config in configurations:
                if 'name' in each_config:
                    if each_config['name'] == config_name:
                        config_detail['Found'] = True
                        config_detail['details'] = each_config
                    else:
                        pass
                else:
                    pass
        else:
            pass

        return config_detail

    def doCliPipelineMerge(self, onboard_object, create_mode=True, merge_type="pm"):
        """
        Function to use Akamai property-manager CLI and merge template
        """
        #For PM merge, it will use temp_pm folder
        #For CPS merge, it will use temp_cps folder
        #Delete these folders if they exist to start

        FILE = open('command_output', 'w')   

        if os.path.exists('temp_pm'):
            shutil.rmtree('temp_pm')
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


        try:
            if create_mode:
                #Build projectInfo contents
                projectInfo = dict(environments = ['test'], name = 'temp_' + merge_type)

                #Create pipeline specific folders are files
                if not os.path.exists(os.path.join('temp_' + merge_type,'dist')):
                    os.makedirs(os.path.join('temp_' + merge_type,'dist'))
                if not os.path.exists(os.path.join('temp_' + merge_type,'environments','test')):
                    os.makedirs(os.path.join('temp_' + merge_type,'environments','test'))
                if not os.path.exists(os.path.join('temp_' + merge_type,'templates')):
                    os.makedirs(os.path.join('temp_' + merge_type,'templates'))
                with open(os.path.join('temp_' + merge_type,'projectInfo.json'),'w') as projectFile:
                    projectFile.write(json.dumps(projectInfo, indent=4))

                if merge_type == "pm":
                    templateFile = onboard_object.source_template_file
                    valuesFile = onboard_object.source_values_file
                else:
                    templateFile = onboard_object.ssl_cert_template_file
                    valuesFile = onboard_object.ssl_cert_template_values

                #Create main.json with contents of templateContent
                with open(templateFile,'r') as templateHandler:
                    templateData = json.load(templateHandler)
                with open(os.path.join('temp_' + merge_type,'templates','main.json'),'w') as mainContentHandler:
                    mainContentHandler.write(json.dumps(templateData, indent=4))

                #create values file for test env from variables
                with open(valuesFile,'r') as valuesHandler, \
                     open(os.path.join('temp_' + merge_type,'environments','test','variables.json'),'w') as testValuesHandler:
                    value_json = valuesHandler.read()
                    testValuesHandler.write(value_json)

                #prepare the variable definitions file contents
                varDefinitions = {}
                varDefinitions['definitions'] = {}
                for eachKey in json.loads(value_json).keys():
                    varDefinitions['definitions'][eachKey] = {}
                    varDefinitions['definitions'][eachKey]['default'] = ""
                    varDefinitions['definitions'][eachKey]['type'] = "userVariableValue"

                with open(os.path.join('temp_' + merge_type,'environments','variableDefinitions.json'),'w') as definitionHandler:
                    definitionHandler.write(json.dumps(varDefinitions, indent=4))

                #Create envInfo.json else it will error out
                testEnvInfo = dict(name = "test")
                with open(os.path.join('temp_' + merge_type,'environments','test','envInfo.json'),'w') as testValuesHandler:
                    testValuesHandler.write(json.dumps(testEnvInfo, indent=4))

                #Run pipeline merge
                if merge_type == "pm":
                    command = ['akamai', 'pipeline', 'merge', '-n', '-p', 'temp_pm', 'test', '--edgerc', onboard_object.edgerc, '--section', onboard_object.section]
                    child_process = subprocess.Popen(command, 
                                        stdout=subprocess.PIPE, 
                                        stderr=subprocess.STDOUT)
                    stdout,stderr = child_process.communicate()   
                    rtn_code = child_process.returncode               
                else:
                    command = ['akamai', 'pipeline', 'merge', '-n', '-p', 'temp_cps', 'test', '--edgerc', onboard_object.edgerc, '--section', onboard_object.section]
                    child_process = subprocess.Popen(command, 
                                        stdout=subprocess.PIPE, 
                                        stderr=subprocess.STDOUT)
                    stdout,stderr = child_process.communicate()   
                    rtn_code = child_process.returncode                  
            else:
                #Copy the folder and run pipeline merge
                copy_tree(onboard_object.folder_path, 'temp_pm')

                #Read the projectInfo file to update the name of it
                with open(os.path.join('temp_pm', 'projectInfo.json'), 'r') as f:
                    content = json.loads(f.read())
                    content['name'] = 'temp_pm'

                #Write the projectInfo file with updated name
                with open(os.path.join('temp_pm', 'projectInfo.json'), 'w') as f:
                    f.write(json.dumps(content, indent=4))

                command = ['akamai', 'pipeline', 'merge', '-n', '-p', 'temp_pm', onboard_object.env_name,'--edgerc', onboard_object.edgerc, '--section', onboard_object.section]                
    
                child_process = subprocess.Popen(command, 
                                    stdout=subprocess.PIPE, 
                                    stderr=subprocess.STDOUT)
                stdout,stderr = child_process.communicate()   
                rtn_code = child_process.returncode               

            #if pipeline merge command was not successful, return false
            if rtn_code != 0:
                print('\n Merging the template file failed')
                print(stdout)
                print(stderr)
                return False
            
            #process call worked, return true
            return True

        except Exception as e:
            print(e)
            print('\nERROR: Exception occurred while trying to merge. Check devops-logs.log and/or temp_* folder to see if files were copied or merged correctly')
            return False
                
