from __future__ import annotations

import csv
import ipaddress
import json
import os
import platform
import random
import shutil
import socket
import ssl
import string
import subprocess
import sys
from datetime import datetime
from functools import reduce
from pathlib import Path
from time import gmtime
from time import strftime

import forcediphttpsadapter
import openpyxl
import OpenSSL.crypto
import pandas as pd
import requests
import urllib3
import util_emojis as emoji
from exceptions import setup_logger
from forcediphttpsadapter.adapters import ForcedIPHTTPSAdapter
from poll import pollActivation
from requests.adapters import HTTPAdapter
from xlsx_util import auto_adjust_xlsx_column_width

logger = setup_logger()
space = ' '
column_width = 50


class smoketestFunctions:

    def __init__(self, session):
        self.session = session
        self.status_mappings = {0: 'Success',
                                1: 'Fail_DNS_FormErr',
                                3: 'Fail_DNS_NXDomain',
                                2: 'Fail_DNS_ServFail'}

    def dns_lookup(self, resolve, type=None):
        jsonResp = False
        url = 'https://dns.google/resolve'  # ?name=example.com&type=a&do=1'
        params = {
            'name': resolve
        }
        if type:
            params['type'] = type

        resp = self.session.get(url, params=params)
        if resp.status_code == 200:
            jsonResp = resp.json()

        return jsonResp
        # jsonResp[]
        # if jsonResp['Status'] != 0:

    def check_ehn_dns(self, smoketest_object):
        for hostname in smoketest_object.unique_hostnames:
            ehn_status = 'Error_Looking_Up_EHN_Check_Manually'
            dnsResp = self.dns_lookup(smoketest_object.hostname_dict[hostname]['edgeHostname'])

            if dnsResp:
                try:
                    ehn_status = self.status_mappings[int(dnsResp['Status'])]
                    if ehn_status == 'Success':
                        ehn_status = 'Edge_Hostname_Created'
                        logger.info(f"{space}{emoji.pass_green} {smoketest_object.hostname_dict[hostname]['edgeHostname']:<30} created")
                except:
                    logger.error(f"{space}{emoji.fail} {smoketest_object.hostname_dict[hostname]['edgeHostname']:<30} does not exist")

            smoketest_object.hostname_dict[hostname]['edgeHostname_Status'] = ehn_status

    def check_acme_dns(self, smoketest_object):
        for hostname in smoketest_object.unique_hostnames:
            acme_record = (list(filter(lambda x: x['cnameFrom'] == hostname, smoketest_object.acme_challenges)))
            try:
                acme_record = acme_record[0]
            except:
                acme_record = 'ACME_Hostname_Not_Found'
                logger.info(f'{space}{emoji.fail} acme token does not exist for {hostname}')
                logger.info(f'{space}{space}{emoji.key} sbd_record:  _acme-challenge.{hostname}')
                logger.info(f'{space}{space}{emoji.dart} sbd_target: {acme_record['validationCname']['target']}')

            smoketest_object.hostname_dict[hostname]['acmeTarget'] = acme_record['validationCname']['target']

            acme_status = 'ACME_Does_Not_Exist'

            dnsResp = self.dns_lookup(f'_acme-challenge.{hostname}')
            try:
                acme_status = self.status_mappings[int(dnsResp['Status'])]
            except:
                acme_status = 'Error_Looking_Up_ACME_Check_Manually'
                logger.info(f'{space}{emoji.fail} acme token does not exist for {hostname}')
                logger.info(f'{space}{space}{emoji.key} sbd_record:  _acme-challenge.{hostname}')
                logger.info(f'{space}{space}{emoji.dart} sbd_target: {acme_record['validationCname']['target']}')

            if int(dnsResp['Status']) == 0:
                target = f"{acme_record['validationCname']['target']}."
                target_exists = (list(filter(lambda x: x['data'] == target, dnsResp['Answer'])))
                if len(target_exists) > 0:
                    acme_status = 'ACME_Record_Exists'
                    logger.info(f'{space}{emoji.pass_green} ACME token does exists for _acme-challenge.{hostname}')
            else:
                logger.info(f'{space}{emoji.fail} acme token does not exist for {hostname}')
                logger.info(f'{space}{space}{emoji.key} sbd_record:  _acme-challenge.{hostname}')
                logger.info(f'{space}{space}{emoji.dart} sbd_target:  {acme_record['validationCname']['target']}')

            smoketest_object.hostname_dict[hostname]['acmeStatus'] = acme_status

    def hostname_status_check(self, smoketest_object):
        hostname_dict = {}
        smoketest_object.unique_hostnames = list(set(list(map(lambda x: x['hostname'], smoketest_object.csv_dict))))

        # get acme challenges
        for hostname in smoketest_object.unique_hostnames:
            hostname_dict[hostname] = {}

            hostname_status = (list(filter(lambda x: x['cnameFrom'] == hostname, smoketest_object.all_account_hostnames)))

            if hostname_status:
                if len(hostname_status) > 1:
                    combined_status = reduce(lambda a, b: dict(a, **b), hostname_status)
                else:
                    combined_status = hostname_status[0]

                hostname_dict[hostname]['propertyName'] = combined_status['propertyName']
                logger.info(f'{space}{emoji.pass_green} {hostname:<30} found{space:>20}property: {combined_status['propertyName']}')
                try:
                    hostname_dict[hostname]['status'] = 'production_property_found'
                    hostname_dict[hostname]['certType'] = combined_status['productionCertType']
                    hostname_dict[hostname]['edgeHostname'] = combined_status['productionCnameTo']
                except KeyError:
                    hostname_dict[hostname]['status'] = 'only_staging_property_found'
                    hostname_dict[hostname]['certType'] = combined_status['stagingCertType']
                    hostname_dict[hostname]['edgeHostname'] = combined_status['stagingCnameTo']
                    logger.info(f'  {space}{emoji.fail} hostname only active on staging!')
            else:
                logger.error(f'{space}{emoji.thumbdown} hostname not found {emoji.shrug} {hostname}')
                hostname_dict[hostname]['status'] = 'not_found'
                hostname_dict[hostname]['edgeHostname'] = 'not_found'
                hostname_dict[hostname]['certType'] = 'not_found'

        smoketest_object.hostname_dict = hostname_dict

    def certificate_check(self, smoketest_object):
        for hostname in smoketest_object.unique_hostnames:
            if smoketest_object.hostname_dict[hostname]['edgeHostname_Status'] == 'Success':
                lookup_edgehostname = smoketest_object.hostname_dict[hostname]['edgeHostname']
            else:
                lookup_edgehostname = 'a1998.b.akamai.net'

            certJson = self.lookupHost(hostname, lookup_edgehostname)
            if certJson:
                if certJson['issuer'] == "Let's Encrypt":
                    logger.info(f'{space}{emoji.pass_green} {hostname} returns Lets Encrypt certificate!')
                    logger.info(f'{space}{space}{emoji.star} CN: {certJson['commonName']}')
                    logger.info(f'{space}{space}{emoji.star} Issuer_CA: {certJson['issuer']}')
                    logger.info(f'{space}{space}{emoji.star} Issued: {certJson['not_before']}')
                    logger.info(f'{space}{space}{emoji.star} Expires: {certJson['not_after']}')
                    logger.info(f'{space}{space}{emoji.star} Serial: {certJson['serial_number']}')
                    logger.info(f'{space}{space}{emoji.star} {hostname} returns Lets Encrypt certificate!')
                    smoketest_object.hostname_dict[hostname]['certificateIssuer'] = certJson['issuer']
                    smoketest_object.hostname_dict[hostname]['certificateIssued'] = True
                    smoketest_object.hostname_dict[hostname]['certificateExpiry'] = certJson['not_after']
                else:
                    logger.error(f'{space}{emoji.pass_green} {hostname} returns non-SBD certificate')
                    logger.info(f'{space}{space}{emoji.star} CN: {certJson['commonName']}')
                    logger.info(f'{space}{space}{emoji.star} Issuer_CA: {certJson['issuer']}')
                    logger.info(f'{space}{space}{emoji.star} Issued: {certJson['not_before']}')
                    logger.info(f'{space}{space}{emoji.star} Expires: {certJson['not_after']}')
                    logger.info(f'{space}{space}{emoji.star} Serial: {certJson['serial_number']}')
                    smoketest_object.hostname_dict[hostname]['certificateIssuer'] = certJson['issuer']
                    smoketest_object.hostname_dict[hostname]['certificateIssued'] = True
                    smoketest_object.hostname_dict[hostname]['certificateExpiry'] = certJson['not_after']

            else:
                logger.error(f'{space}{emoji.fail} {hostname} no certificate deployed')
                smoketest_object.hostname_dict[hostname]['certificateIssuer'] = ''
                smoketest_object.hostname_dict[hostname]['certificateIssued'] = False
                smoketest_object.hostname_dict[hostname]['certificateExpiry'] = ''

    def status_code_check(self, smoketest_object):
        for test in smoketest_object.csv_dict:
            if smoketest_object.hostname_dict[test['hostname']]['edgeHostname_Status'] == 'Success':
                lookup_edgehostname = smoketest_object.hostname_dict[test['hostname']]['edgeHostname']
            else:
                lookup_edgehostname = 'a1410.dscb.akamai.net'

            ehn_dns_lookup_resp = self.dns_lookup(lookup_edgehostname, 'A')
            if int(ehn_dns_lookup_resp['Status']) == 0:
                for resp in ehn_dns_lookup_resp['Answer']:
                    try:
                        ipaddress.ip_address(resp['data'])
                        lookup_ipaddress = resp['data']
                        continue
                    except ValueError:
                        pass
            else:
                logger.error(f'{space}{space}{emoji.fail} unable to get spoofing IP')
                test['https_status_code'] = 'no_spoofing_ip_found'
                test['http_status_code'] = 'no_spoofing_ip_found'
                continue

            hostname = f'{test['hostname']}'
            scope = f'{test['scope']}'
            request = f'{hostname}{scope}'
            print()
            logger.info(f'{space}{emoji.file_folder} {request}')
            for secure in [True, False]:
                status_code, success, test_url = self.httpTest(hostname, scope, lookup_edgehostname, secure, lookup_ipaddress)
                if secure:
                    if success == 'Fail':
                        logger.error(f'{space}{space}{emoji.fail} HTTPS returned {status_code}')
                    else:
                        logger.info(f'{space}{space}{emoji.pass_green} HTTPS returned {status_code}')
                    test['https_status_code'] = f'{success} - {status_code} - {test_url}'
                else:
                    if success == 'Fail':
                        logger.error(f'{space}{space}{emoji.fail} HTTP  returned {status_code}')
                    else:
                        logger.info(f'{space}{space}{emoji.pass_green} HTTP  returned {status_code}')
                    test['http_status_code'] = f'{success} - {status_code} - {test_url}'

    def parsePEM(self, pemStr, returnJson=False):
        x509 = OpenSSL.crypto.load_certificate(OpenSSL.crypto.FILETYPE_PEM, pemStr)
        date_format, encoding = '%Y%m%d%H%M%SZ', 'ascii'
        not_before = datetime.strptime(x509.get_notBefore().decode(encoding), date_format)
        not_after = datetime.strptime(x509.get_notAfter().decode(encoding), date_format)
        issuer = x509.get_issuer().organizationName

        serial_number = f'{x509.get_serial_number():x}'
        commonName = x509.get_subject().CN

        now = datetime.now()

        days_since_signed = now - not_before
        days_since_signed = days_since_signed.days

        days_until_expiration = not_after - now
        days_until_expiration = days_until_expiration.days

        if returnJson:
            return {'commonName': commonName,
                    'issuer': issuer,
                    'not_before': str(not_before),
                    'not_after': str(not_after),
                    'serial_number': serial_number,
                    'days_since_signed': days_since_signed,
                    'days_until_expiration': days_until_expiration
                    }

        else:
            return (commonName, issuer, not_before, not_after, serial_number, days_since_signed, days_until_expiration)

    def getSession(self, protocol, hostname, lookup_ipaddress, secure):
        # function to set http request session and set SNI header for https
        session = requests.Session()
        if secure:
            session.mount(f'{protocol}{hostname}', ForcedIPHTTPSAdapter(dest_ip=lookup_ipaddress))

        return session

    def lookupHost(self, hostname, edgehost, debug=False):
        # logOKHeader(f"#using DNS to find certificate for hostname: {hostname}")
        context = ssl.create_default_context()

        # we don't care if a cert is not signed or expired
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE

        connectHostname = hostname

        if edgehost is not None:
            connectHostname = edgehost

        with context.wrap_socket(socket.socket(socket.AF_INET), server_hostname=hostname) as conn:
            try:
                conn.connect((connectHostname, 443))
                cert = conn.getpeercert(True)
                certificate = ssl.DER_cert_to_PEM_cert(cert)
            except:
                # logFailStatus(f"failed: TLS on connecting hostname for {connectHostname} using host {hostname}")
                certificate = []
            if certificate:
                jsonDict = self.parsePEM(certificate, returnJson=True)
                # print(json.dumps(jsonDict, indent=3))
                return jsonDict
            else:
                return False

    def httpTest(self, hostname=None, scope=None, edgehost=None, secure=False, lookup_ipaddress=None):

        protocol = 'http://'
        url = f'{protocol}{edgehost}{scope}'
        if secure:
            protocol = 'https://'
            url = f'{protocol}{hostname}{scope}'

        # remove * from scope
        if scope.endswith('*'):
            scope = scope.replace('*', '')

        # generate random string (query smoketest={random_string}) and set query param
        string_length = 7
        random_string = ''.join(random.choices(string.ascii_letters, k=string_length))
        params = {
            'smoketest': random_string
        }

        # make smoke test request
        session = self.getSession(protocol, hostname, lookup_ipaddress, secure)
        # valid success status codes
        success_status_codes = [200, 404, 201, 301, 302, 403]
        smoke_test_success = 'Fail'
        try:
            apiResponseDetails = session.get(url, headers={'Host': hostname}, params=params, allow_redirects=False, timeout=10, verify=True)
            output = apiResponseDetails.status_code
            if output in success_status_codes:
                smoke_test_success = 'Success'
        except requests.exceptions.SSLError:
            smoke_test_success = 'Fail'
            output = 'SSL_CERTIFICATE_ERROR'

        return (output, smoke_test_success, f'{protocol}{hostname}{scope}?smoketest={random_string}')

    def buildOutputXLSX(self, smoketest_object, directory: str):
        filename = os.path.basename(smoketest_object.csv_loc)
        filename_without_extension = os.path.splitext(filename)[0]
        filename = f'{directory}/{filename_without_extension}_output.xlsx'
        data_frame_hostname = pd.DataFrame(smoketest_object.hostname_dict).T
        data_frame_hostname.index.name = 'hostname'
        data_frame_scope = pd.DataFrame(smoketest_object.csv_dict)
        data_frame_scope.index = data_frame_scope.index + 1
        sheet = {}
        sheet['hostname_status'] = data_frame_hostname
        sheet['scope_testing'] = data_frame_scope
        write_xlsx(filename, sheet, show_index=True)
        open_excel_application(filename, True, data_frame_hostname)
        return (filename)

    def buildOutputXLS_sbd_precheck(self, smoketest_object, filename: str, directory: str,
                                    launch: bool | None = True):
        now = datetime.now()
        dt_string = now.strftime('%Y%m%d_%H%M_')
        filename = f'{directory}/{dt_string}{filename}'
        data_frame_hostname = pd.DataFrame(smoketest_object.hostname_dict).T
        data_frame_hostname.index.name = 'hostname'
        sheet = {'hostname_status': data_frame_hostname}
        write_xlsx(filename, sheet, show_index=True)
        if launch:
            open_excel_application(filename, data_frame_hostname)
        return (filename)

    def buildOutputcsv_sbd_tokens_only(self, token_dict, filename: str, directory: str):
        now = datetime.now()
        dt_string = now.strftime('%Y%m%d_%H%M_')
        filename = f'{directory}/{dt_string}{filename}'
        data_frame_hostnames = pd.DataFrame(token_dict)
        data_frame_hostnames.to_csv(filename, index=False)
        return (filename)

    def getHostnamesFromCsv(self, smoketest_object):
        hostnames = []
        try:
            with open(f'{smoketest_object.csv_loc}', encoding='utf-8-sig', newline='') as csvinput:
                for row in csv.DictReader(csvinput):
                    hostnames.append(row['hostname'])
        except FileNotFoundError as e:
            print()
            sys.exit(logger.error(e, exc_info=False))

        smoketest_object.unique_hostnames = hostnames

    def check_acme_dns_sbd_precheck(self, smoketest_object):

        hostnameDict = {}
        for hostname in smoketest_object.unique_hostnames:
            acme_status = 'ACME-Does-Not-Exist'
            hostnameDict[hostname] = {}
            msg = f'_acme-challenge.{hostname}'
            acme_record = (list(filter(lambda x: x['cnameFrom'] == hostname, smoketest_object.acme_challenges)))

            try:
                acme_record = acme_record[0]
                acme_hostname = acme_record['validationCname']['hostname']
                acme_target = acme_record['validationCname']['target']
            except:
                acme_record = 'ACME-Hostname-Not-Found'
                acme_target = 'not_found'
                acme_hostname = f'_acme-status.{hostname}'
                logger.error(f'{emoji.fail} {msg} Error! Token not returned from PAPI')

            dnsResp = self.dns_lookup(acme_record['validationCname']['hostname'])
            try:
                acme_status = self.status_mappings[int(dnsResp['Status'])]
            except:
                acme_status = 'Error-Looking-Up-ACME-Check-Manually'
                logger.error(f'{emoji.fail} {msg} ACME record does not exist')

            if int(dnsResp['Status']) == 0:
                try:
                    target_exists = (list(filter(lambda x: x['data'] == f'{acme_target}.', dnsResp['Answer'])))
                    if len(target_exists) > 0:
                        acme_status = 'ACME-Record-Exists'
                        logger.info(f'{emoji.pass_green} {msg} Success! ACME record exists')
                    else:
                        acme_status = 'ACME-Record_Invalid'
                        logger.warn(f'{emoji.fail} {msg} ACME record invalid')
                except:
                    acme_status = 'Fail_Record_Not_Present'
                    acme_target = acme_record['validationCname']['target']
                    logger.error(f'{emoji.fail} {msg} ACME record does not exist')

            else:
                acme_target = acme_record['validationCname']['target']
                logger.error(f'{emoji.fail} {msg} ACME record does not exist')

            hostnameDict[hostname]['acmeStatus'] = acme_status
            hostnameDict[hostname]['acme_hostname'] = acme_hostname
            hostnameDict[hostname]['acme_record'] = acme_target

        smoketest_object.hostname_dict = hostnameDict


def write_xlsx(filepath: str, dict_value: dict,
            freeze_row: int | None = 1,
            freeze_column: int | None = 2,
            show_url: bool | None = True,
            show_index: bool | None = False,
            adjust_column_width: bool | None = True) -> None:
    with pd.ExcelWriter(path=filepath, engine='xlsxwriter',
                    engine_kwargs={'options': {'strings_to_urls': show_url}}) as writer:
        writer.book.use_zip64()  # to allow excel to store files larger than 4GB
        MAX_XLXS_ROW = 1000000   # 1 million rows per sheet
        MAX_SHEETS = 89          # 89 sheets per excel
        for sheetname, df in dict_value.items():
            if df is not None:
                if len(df.index) <= MAX_XLXS_ROW:
                    df.to_excel(writer, sheet_name=sheetname,
                                freeze_panes=(freeze_row, freeze_column),
                                index=show_index)
                    workbook = writer.book
                    cell_format = workbook.add_format({'bold': True,
                                                    'text_wrap': True,
                                                    'valign': 'top',
                                                    'align': 'left',
                                                    'fg_color': 'blue',
                                                    'border': 1,
                                                    })
                    header_format = workbook.add_format({'bold': True,
                                                        'text_wrap': True,
                                                        'valign': 'top',
                                                        'align': 'middle',
                                                        'fg_color': '#FFC588',  # orange
                                                        'border': 1,
                                                        })

                    # Write the column headers with the defined format.
                    ws = writer.sheets[sheetname]
                    ws.hide_gridlines()
                    for col_num, value in enumerate(df.columns.values):
                        if show_index:
                            ws.write(0, col_num + 1, value, header_format)
                        else:
                            ws.write(0, col_num, value, header_format)
                    format1 = workbook.add_format({'num_format': '#,##0'})
                    ws.set_column(2, 2, None, format1)
                    ws.autofit()
                else:
                    total, last_sheet = divmod(len(df.index), MAX_XLXS_ROW)
                    logger.debug(f'{total=} {last_sheet=} dataset={len(df.index)}')
                    if last_sheet <= MAX_XLXS_ROW:
                        for sheet in (n + 1 for n in range(total + 1)):
                            logger.debug(f'Sheet{sheet}')

                            sheet_no = sheet
                            logger.info(f'{sheetname}_{sheet_no}')
                            if sheet == 1:
                                first_row = 0
                                last_row = (sheet * MAX_XLXS_ROW) + 1
                            else:
                                first_row = last_row + 1
                                last_row = len(df.index)

                            if sheet == total + 1 and last_sheet > 0:
                                logger.debug(f'{total=} {sheet_no=} {sheet=}')
                                sheet_no = total + 1
                            logger.warning(f'Sheet{sheet}: from {first_row} to {last_row}')
                            df.iloc[first_row:last_row].to_excel(writer, sheet_name=f'{sheetname}_{sheet_no}')

                            '''
                            df.to_excel(writer, sheet_name=f'{sheetname}_{sheet_no}',
                                        freeze_panes=(freeze_row, freeze_column),
                                        index=show_index)
                            '''
                            if adjust_column_width is True:
                                auto_adjust_xlsx_column_width(df, writer, sheet_name=f'{sheetname}_{sheet_no}',
                                                        index=show_index)

                            workbook = writer.book
                            cell_format = workbook.add_format()
                            cell_format.set_bold()
                            cell_format.set_font_color('blue')
                            cell_format.set_text_wrap()

                            header_format = workbook.add_format({'bold': True,
                                                                'text_wrap': True,
                                                                'valign': 'top',
                                                                'align': 'middle',
                                                                'fg_color': '#FFC588',  # orange
                                                                'border': 1,
                                                                })

                            # Write the column headers with the defined format.
                            ws = writer.sheets[f'{sheetname}_{sheet_no}']
                            for col_num, value in enumerate(df.columns.values):
                                if show_index:
                                    ws.write(0, col_num + 1, value, header_format)
                                else:
                                    ws.write(0, col_num, value, header_format)

                            format1 = workbook.add_format({'num_format': '#,##0'})
                            ws.set_column(2, 2, None, format1)
                            ws.autofit()


def open_excel_application(filepath: str,
                           df: pd.DataFrame | None = None) -> None:
    if platform.system() == 'Darwin':
        if len(df.index) > 0:
            subprocess.check_call(['open', '-a', 'Microsoft Excel', filepath])
