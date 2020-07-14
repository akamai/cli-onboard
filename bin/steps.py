class executionSteps(object):
    #This Class will determine the execution steps based on setup.json values

    def doCreateNewCpCode(self, setup_json_content):
        if setup_json_content['property_info']['default_cpcode']['create_new_cpcode'] is True:
            return True
        else:
            return False

    def doPropertyActivateStaging(self, setup_json_content):
        if setup_json_content['activate_property_staging'] is True:
            return True
        else:
            return False

    def doPropertyActivateProduction(self, setup_json_content):
        if setup_json_content['activate_property_production'] is True:
            return True
        else:
            return False

    def doWafAddSelectedHosts(self, setup_json_content):
        if setup_json_content['update_waf_info']['add_selected_host'] is True:
            return True
        else:
            return False

    def doWafUpdateMatchTarget(self, setup_json_content):
        if setup_json_content['update_waf_info']['update_match_target'] is True:
            return True
        else:
            return False

    def doWafActivateStaging(self, setup_json_content):
        if setup_json_content['activate_waf_policy_staging'] is True:
            return True
        else:
            return False

    def doWafActivateProduction(self, setup_json_content):
        if setup_json_content['activate_waf_policy_production'] is True:
            return True
        else:
            return False

    def doWafAddSelectedHosts(self, setup_json_content):
        if 'update_waf_info' in setup_json_content:
            if setup_json_content['update_waf_info']['add_selected_host'] is True:
                return True
            else:
                return False
        else:
            return False

    def doWafUpdateMatchTarget(self, setup_json_content):
        if 'update_waf_info' in setup_json_content:
            if setup_json_content['update_waf_info']['update_match_target'] is True:
                return True
            else:
                return False
        else:
            return False
