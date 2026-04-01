from __future__ import annotations

from collections import defaultdict

from exceptions import setup_logger
from rich.table import Table


logger = setup_logger()
space = ' '


class sbdFunctions:
    def __init__(self, session) -> None:
        self.session = session

    def get_unique_properties(self, hostname_dict):
        unique_properties = list(set(list(map(lambda x: (x['propertyId'], x['groupId'], x['contractId'], x['propertyName']), hostname_dict))))
        return (unique_properties)

    def get_sbd_hostnames(self, wrapper_object):

        all_hostnames = wrapper_object.get_all_account_hostnames()
        merged_dict = defaultdict(dict)
        merge_key = 'cnameFrom'
        for json_obj in all_hostnames:
            key_value = json_obj.pop(merge_key)
            merged_dict[key_value].update(json_obj)

        # Convert the defaultdict back to a regular dict for output
        merged_output = [{merge_key: key, **value_dict} for key, value_dict in merged_dict.items()]

        sbd_hostnames = list(filter(lambda x: self._is_sbd(x), merged_output))
        sbd_hostnames = self.clean_dict(sbd_hostnames)

        return (list(map(lambda x: {'hostname': x['cnameFrom'],
                                    'staging': x['stagingCertType'],
                                    'production': x['productionCertType'],
                                    'propertyId': x['propertyId'],
                                    'groupId': x['groupId'],
                                    'contractId': x['contractId'],
                                    'propertyName': x['propertyName']}, sbd_hostnames)))

    def _is_sbd(self, x):

        if x.setdefault('stagingCertType', '') == 'DEFAULT' or x.setdefault('productionCertType', '') == 'DEFAULT':
            return (True)
        else:
            return (False)

    def get_papi_hostname_status(self, wrapper_object, unique_properties, hostname_dict):
        hostname_dd = defaultdict(dict)
        for item in hostname_dict:
            key_value = item.pop('hostname')
            hostname_dd[key_value].update(item)

        logger.debug(f'{unique_properties=}')
        for property in unique_properties:
            """x['propertyId'], x['groupId'], x['contractId'], x['propertyName'])"""
            prop_hostnames = wrapper_object.get_property_hostnames(property[0],
                                                                   property[1],
                                                                   property[2])

            if not prop_hostnames:
                continue
            try:
                obj_to_append = [{'hostname': x['cnameFrom'],
                                'stagingStatus': x['certStatus']['staging'][0]['status'],
                                'productionStatus': x['certStatus']['production'][0]['status']
                                }
                                for x in prop_hostnames
                                if x.get('stagingCertType') == 'DEFAULT'
                                ]
            except (KeyError, TypeError):
                logger.error(f'{property=}')

            for hostname_obj in obj_to_append:
                hostname = hostname_obj['hostname']
                hostname_dd[hostname].update(dict({'stagingStatus': hostname_obj['stagingStatus'],
                                                   'productionStatus': hostname_obj['productionStatus']}))

        merged_output = [{'hostname': key, **value_dict} for key, value_dict in hostname_dd.items()]
        return merged_output

    def clean_dict(self, hostname_dict):
        for hostname in hostname_dict:
            hostname.setdefault('stagingCertType', '')
            hostname.setdefault('productionCertType', '')

        return hostname_dict

    def create_output_table(self, rows, stalled_status):
        table = Table(title='Stalled Hostnames', header_style='bold magenta')

        table.add_column('Hostname', justify='left', no_wrap=True)
        table.add_column('propertyId', justify='left', no_wrap=True)
        table.add_column('propertyName', justify='left', no_wrap=True)
        table.add_column('stagingStatus', justify='left', no_wrap=True)
        table.add_column('productionStatus', justify='left', no_wrap=True)

        for row in rows:
            if row['productionStatus'] == 'AWAITING_PRODUCTION_ACTIVATION':
                p_status_text = f"[grey58]{row['productionStatus']}[/grey58]"
            elif row['productionStatus'] in stalled_status:
                p_status_text = f"[red]{row['productionStatus']}[/red]"
            else:
                p_status_text = f"[green]{row['productionStatus']}[/green]"

            if row['stagingStatus'] in stalled_status:
                s_status_text = f"[red]{row['stagingStatus']}[/red]"
            else:
                s_status_text = f"[green]{row['stagingStatus']}[/green]"

            table.add_row(row['hostname'], row['propertyId'], row['propertyName'], s_status_text, p_status_text)

        return (table)
