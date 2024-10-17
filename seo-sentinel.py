__version__ = '0.8.2'
__author__ = 'Enrico Altavilla'

import sys
import os
from enum import Enum
import time
import re
import yaml
import csv

import requests
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup



# Enum with the types of output errors
class EventType(Enum):
    INFO = 1
    CHECK_PASSED = 2
    WARNING = 3
    CHECK_FAILED = 4


# An enum to represent the scope, used for the timestamp
class Scope(Enum):
    PROJECT = 1
    CHECK = 2
    ROW = 3


# CheckResults class to store the results of the checks
class Reporter:
    def __init__(self):
        self.info = False
        self.warning = False
        self.check_passed = False
        self.check_failed = False

        self.info_log = []
        self.warning_log = []
        self.check_passed_log = []
        self.check_failed_log = []
        self.global_log = []

        self.project_name = None
        self.output_options = {}

    def set_project_name(self, project_name):
        self.project_name = project_name
    
    def set_output_options(self, output_options):
        self.output_options = output_options

    def log_info(self, message):
        self.info_log.append(message)
        self.global_log.append(message)
    
    def log_warning(self, message):
        self.warning_log.append(message)
        self.global_log.append(message)

    def log_check_passed(self, message):
        self.check_passed_log.append(message)
        self.global_log.append(message)

    def log_check_failed(self, message):
        self.check_failed_log.append(message)
        self.global_log.append(message)


    def get_info_log(self):
        return self.info_log
    
    def get_warning_log(self):
        return self.warning_log

    def get_check_passed_log(self):
        return self.check_passed_log
    
    def get_check_failed_log(self):
        return self.check_failed_log

    def get_global_log(self):
        return self.global_log


    def handle_output(self, scope, message, output_type):

        # Prepend the project name to the message, if it exists
        if self.project_name:
            message = f"[{self.project_name}] {message}"

        # Prepend the output type to the message
        if output_type == EventType.INFO:
            message = f"[INFO] - {message}"
        elif output_type == EventType.WARNING:
            message = f"[WARNING] - {message}"
        elif output_type == EventType.CHECK_PASSED:
            message = f"[PASSED] - {message}"
        elif output_type == EventType.CHECK_FAILED:
            message = f"[FAILED] - {message}"


        # Prepend the timestamp to the message if enabled
        timestamp = self.output_options.get('timestamp', False)
        if timestamp.get('enabled', False):
            if scope.value <= timestamp.get('frequency', 3):
                timestamp_format = timestamp.get('format', '%Y-%m-%d %H-%M-%S %z %Z')
                message = f"{time.strftime(timestamp_format)} {message}"


        # Gets the list of destinations of the output
        destinations = self.output_options.get('destinations', {})
        
        # Output to console if enabled
        if destinations.get('console', {}).get('enabled', False):
            log_level = destinations.get('console').get('log_level', 'all')
            if log_level == 'all' or (log_level == 'issues' and output_type != EventType.CHECK_PASSED):
                print(message)


        # Store the message in the corresponding logs
        if output_type == EventType.INFO:
            self.log_info(message)
        elif output_type == EventType.WARNING:
            self.log_warning(message)
        if output_type == EventType.CHECK_PASSED:
            self.log_check_passed(message)
        elif output_type == EventType.CHECK_FAILED:
            self.log_check_failed(message)



    def report_info(self, scope, message):
        self.info = True
        self.handle_output(scope, message, EventType.INFO)

    def report_warning(self, scope, message):
        self.warning = True
        self.handle_output(scope, message, EventType.WARNING)

    def report_passed(self, scope, message):
        self.check_passed = True
        self.handle_output(scope, message, EventType.CHECK_PASSED)

    def report_failed(self, scope, message):
        self.check_failed = True
        self.handle_output(scope, message, EventType.CHECK_FAILED)





# HTTPResource class to represent the request and response data
class HTTPResource:
    def __init__(self, request_url, status_code, headers, content):
        self.request_url = request_url
        self.status_code = status_code
        self.headers = headers
        self.content = content




class BaseCheck:
    def __init__(self, name, delay, alert_condition, output_options, base_url=None):
        self.name = name
        self.delay = delay
        self.alert_condition = alert_condition
        self.output_options = output_options
        self.base_url = base_url

    def normalize_url(self, base_url, target_url):
        parsed_target = urlparse(target_url)
        if not parsed_target.netloc:
            return urljoin(base_url, target_url)
        return target_url

    def evaluate_alert_condition(self, results):
        condition_met = False
        if isinstance(results, dict):
            results = list(results.values())

        if isinstance(results, bool):
            if ((self.alert_condition == 'any is true') or (self.alert_condition == 'all is true')) and results:
                condition_met = True
            elif ((self.alert_condition == 'any is false') or (self.alert_condition == 'all is false')) and not results:
                condition_met = True
        elif isinstance(results, list):
            if self.alert_condition == 'any is true' and any(results):
                condition_met = True
            elif self.alert_condition == 'any is false' and any(not result for result in results):
                condition_met = True
            elif self.alert_condition == 'all are true' and all(results):
                condition_met = True
            elif self.alert_condition == 'all are false' and all(not result for result in results):
                condition_met = True

        return condition_met





class RedirectCheck(BaseCheck):
    def __init__(self, name, rules, delay, alert_condition, output_options, base_url=None, expected_redirect_status=[301], max_redirects=5, expected_resource_status=[]):
        super().__init__(name, delay, alert_condition, output_options, base_url)
        self.rules = rules
        self.expected_redirect_status = expected_redirect_status
        self.max_redirects = max_redirects
        self.expected_resource_status = expected_resource_status

    def apply(self):
        issues = {}
        base_url = self.base_url

        reporter.report_info(Scope.CHECK, f"Starting redirect check for '{self.name}' ({len(self.rules)} rules)...")

        for url, expected_destination in self.rules.items():
            if base_url:
                url = self.normalize_url(base_url, url)

            res = self.check_redirect(url, expected_destination)
            issues[url] = res

            time.sleep(self.delay)

        # Evaluate the condition for the alert
        if self.evaluate_alert_condition(issues):
            reporter.report_warning(Scope.CHECK, f"{self.name}: Redirect check failed for one or more URLs.")
        else:
            reporter.report_info(Scope.CHECK, f"{self.name}: Redirect check passed for all URLs.")

        reporter.report_info(Scope.CHECK, f"Finished redirect check for '{self.name}'.")



    def check_redirect(self, start_url, expected_destination):

        expected_destination = self.normalize_url(start_url, expected_destination)

        issues = ""
        current_url = start_url
        hops = 0

        try:
            while hops <= self.max_redirects:
                # Perform the HTTP request without following redirects automatically
                response = requests.get(current_url, allow_redirects=False)
                status_code = response.status_code

                # Use requests' built-in properties to check if the response is a redirect
                if response.is_redirect or response.is_permanent_redirect:
                    # Check if the status code is one of the acceptable redirect status codes
                    if status_code not in self.expected_redirect_status:
                        issues += f"Status code {status_code} is a redirect but not an acceptable one. "
                        break

                    # Get the Location header to find the next URL
                    location_header = response.headers.get('Location')
                    if not location_header:
                        issues += "Location header not found in the response. "
                        break

                    # Normalize the next URL
                    location_header = self.normalize_url(current_url, location_header)

                    # Continue to the next hop
                    current_url = location_header
                    hops += 1

                    if not self.expected_resource_status:
                        # If the expected resource status is not set, we directly check if the location header is the expected destination. This can save us a request.
                        if current_url == expected_destination:
                            reporter.report_passed(Scope.ROW, f"{self.name}: Redirect check passed for '{current_url}'.")
                            return True

                        

                else:
                    # The response is not a redirect, it must be a final status code
                    if current_url != expected_destination:
                        issues += f"Final destination '{current_url}' does not match expected '{expected_destination}'. "
                        break

                    if self.expected_resource_status and status_code not in self.expected_resource_status:
                        # Final response did not match the expected status
                        issues += f"Final status code {status_code} does not match expected {self.expected_resource_status}. "
                        break
                    else:
                        # Success: the final status code is one of the expected codes
                        reporter.report_passed(Scope.ROW, f"{self.name}: Redirect check passed for '{current_url}'.")
                        return True  # No issues


            # If we exit the loop, it means we either hit the max redirects or found an issue
            if hops > self.max_redirects:
                issues += f"Max redirects exceeded ({self.max_redirects}). "

            # Report any accumulated issues
            if issues:
                reporter.report_failed(Scope.ROW, f"{self.name}: Redirect check failed for '{start_url}'. Reason: {issues}")
                return False  # There were issues

        except requests.RequestException as e:
            reporter.report_failed(Scope.ROW, f"{self.name}: HTTP request failed for '{start_url}'. Exception: {str(e)}")
            return False  # There were issues






class MarkupCheck(BaseCheck):
    def __init__(self, name, urls, rules, delay, alert_condition, output_options, base_url=None, parser='lxml'):
        super().__init__(name, delay, alert_condition, output_options, base_url)
        self.urls = urls
        self.rules = rules
        self.parser = parser

    def apply(self):
        issues = {}
        base_url = self.base_url

        reporter.report_info(Scope.CHECK, f"Starting markup check for '{self.name}'...")

        for url in self.urls:
            if base_url:
                url = self.normalize_url(base_url, url)
            try:
                response = requests.get(url)
                http_resource = HTTPResource(url, response.status_code, response.headers, response.text)
                res = self.check_markup(http_resource)
                issues[url] = res
            except requests.RequestException as e:
                reporter.report_failed(Scope.ROW, f"{self.name}: HTTP error for '{url}': {str(e)}")
                issues[url] = True
            except Exception as e:
                reporter.report_failed(Scope.ROW, f"{self.name}: Unexpected error for '{url}': {str(e)}")
                issues[url] = True
            finally:
                time.sleep(self.delay)

        if True in issues.values():
            reporter.report_warning(Scope.CHECK, f"{self.name}: Markup check failed for one or more URLs.")
        else:
            reporter.report_info(Scope.CHECK, f"{self.name}: Markup check passed for all URLs.")

        reporter.report_info(Scope.CHECK, f"Finished markup check for '{self.name}'.")


    def check_markup(self, resource):
        soup = BeautifulSoup(resource.content, self.parser)
        rules_results = []

        for rule in self.rules:
            rule_name = rule.get('name', None)
            selector = rule.get('selector', None)
            expected_count = rule.get('count', None)
            attribute = rule.get('attribute', None)
            attribute_literal = rule.get('attribute_literal', None)
            attribute_regex = rule.get('attribute_regex', None)
            content_literal = rule.get('content_literal', None)
            content_regex = rule.get('content_regex', None)

            # Replace placeholder in attribute_literal or attribute_regex with the checked URL
            if attribute_literal:
                attribute_literal = attribute_literal.replace('{{checked_url}}', resource.request_url)

            if attribute_regex:
                attribute_regex = attribute_regex.replace('{{checked_url}}', resource.request_url)

            match_count = 0
            elements = soup.select(selector)

            if attribute and attribute_literal:
                match_count += sum(1 for element in elements if element.get(attribute, '') == attribute_literal)

            if attribute and attribute_regex:
                pattern = re.compile(attribute_regex)
                match_count += sum(1 for element in elements if pattern.match(element.get(attribute, '')))

            if content_literal:
                match_count += sum(1 for element in elements if element.get_text(strip=True) == content_literal)

            if content_regex:
                content_pattern = re.compile(content_regex)
                match_count += sum(1 for element in elements if content_pattern.search(element.get_text(strip=True)))

            count_match = self.check_count_condition(match_count, expected_count)
            if self.evaluate_alert_condition(count_match):
                reporter.report_failed(Scope.ROW, f"{self.name} > {rule_name}: Markup check failed for '{resource.request_url}'")
            else:
                reporter.report_passed(Scope.ROW, f"{self.name} > {rule_name}: Markup check passed for '{resource.request_url}'")

            rules_results.append(count_match)

        return self.evaluate_alert_condition(rules_results)


    def check_count_condition(self, match_count, count):
        lower_bound, upper_bound = None, None
        if count:
            if ':' in count:
                parts = count.split(':')
                lower_bound = int(parts[0]) if parts[0] else None
                upper_bound = int(parts[1]) if parts[1] else None
            else:
                lower_bound = upper_bound = int(count)

        if lower_bound is not None and match_count < lower_bound:
            return False
        if upper_bound is not None and match_count > upper_bound:
            return False

        return True





class ContentMatchCheck(BaseCheck):
    def __init__(self, name, rules, comparison_method, delay, alert_condition, output_options, base_url=None):
        super().__init__(name, delay, alert_condition, output_options, base_url)
        self.rules = rules
        self.comparison_method = comparison_method

    def apply(self):
        issues = {}

        reporter.report_info(Scope.CHECK, f"Starting content match check for '{self.name}'...")

        for first_resource, second_resource in self.rules.items():
            first_content = self.get_resource_content(first_resource)
            if first_content is None:
                issues[first_resource] = True
                continue

            second_content = self.get_resource_content(second_resource)
            if second_content is None:
                issues[second_resource] = True
                continue

            if self.comparison_method == 'strip_whitespace':
                first_content = '\n'.join([line.strip() for line in first_content.split('\n') if line.strip()])
                second_content = '\n'.join([line.strip() for line in second_content.split('\n') if line.strip()])

            same = first_content == second_content

            if self.evaluate_alert_condition(same):
                issues[first_resource] = True
                reporter.report_failed(Scope.ROW, f"{self.name}: Content match check failed for '{first_resource}' and '{second_resource}'")
            else:
                issues[first_resource] = False
                reporter.report_passed(Scope.ROW, f"{self.name}: Content match check passed for '{first_resource}' and '{second_resource}'")

            time.sleep(self.delay)

        if not self.evaluate_alert_condition(issues):
            reporter.report_warning(Scope.CHECK, f"{self.name}: Content match check failed for one or more URLs.")
        else:
            reporter.report_info(Scope.CHECK, f"{self.name}: Content match check passed for all URLs.")

        reporter.report_info(Scope.CHECK, f"Finished content match check for '{self.name}'.")


    def get_resource_content(self, url):
        if url.startswith('http') or url.startswith('https'):
            try:
                response = requests.get(url)
                return response.text
            except requests.RequestException as e:
                reporter.report_failed(Scope.ROW, f"{self.name}: HTTP error for {url}: {str(e)}")
            except Exception as e:
                reporter.report_failed(Scope.ROW, f"{self.name}: Unexpected error for {url}: {str(e)}")
        else:
            try:
                with open(url, 'r') as file:
                    return file.read()
            except FileNotFoundError:
                reporter.report_failed(Scope.ROW, f"{self.name}: File '{url}' not found.")





# Configuration handler class to parse the YAML configuration file
class ConfigurationHandler:
    def __init__(self, config_file_path):
        self.config_file_path = config_file_path

        with open(self.config_file_path, 'r') as file:
            self.config = yaml.safe_load(file)

        self.project_name = self.config.get('project_name', 'Test Project')
        self.output_options = self.config.get('output', {})

    def get_project_name(self):
        return self.project_name

    def get_output_options(self):
        return self.output_options

    def resolve_path_from_config(self, relative_path):
        config_dir = os.path.dirname(os.path.realpath(self.config_file_path))
        
        resolved_path = os.path.join(config_dir, relative_path)
        
        return os.path.realpath(resolved_path)


    def resolve_path_in_dict(self, dict):
        updated_rules = {}

        for key, value in dict.items():
            if not key.startswith(('http://', 'https://')):
                resolved_key = self.resolve_path_from_config(key)
            else:
                resolved_key = key

            if not value.startswith(('http://', 'https://')):
                resolved_value = self.resolve_path_from_config(value)
            else:
                resolved_value = value

            updated_rules[resolved_key] = resolved_value

        return updated_rules


    def parse_csv_rules(self, csv_file, has_header=False):
        rules = {}

        csv_file = self.resolve_path_from_config(csv_file)

        try:
            with open(csv_file, 'r') as file:
                reader = csv.reader(file)
                if has_header:
                    next(reader, None)
                for row in reader:
                    if len(row) >= 2:
                        source, destination = row[0], row[1]
                        rules[source] = destination
        except FileNotFoundError:
            reporter.report_warning(Scope.PROJECT, f"CSV file '{csv_file}' not found.")

        return rules


    def parse_checks(self):
        checks = []

        for check_data in self.config['checks']:
            if check_data.get('enabled', True) == False:
                continue

            name = check_data['name']
            check_type = check_data['type']
            delay = check_data.get('delay', 0)
            alert_condition = check_data['alert_condition']
            base_url = check_data.get('base_url', None)
            output_options = self.output_options

            if check_type == 'redirect':
                rules = check_data.get('rules', {})
                expected_redirect_status = check_data.get('expected_redirect_status', [301])
                max_redirects = check_data.get('max_redirects', 5)
                expected_resource_status = check_data.get('expected_resource_status', [])
                rules_csv = check_data.get('rules_csv', None)
                if rules_csv:
                    csv_file = rules_csv.get('file', None)
                    has_header = rules_csv.get('has_header', False)
                    if csv_file:
                        rules.update(self.parse_csv_rules(csv_file, has_header))
                check = RedirectCheck(name, rules, delay, alert_condition, output_options, base_url, expected_redirect_status, max_redirects, expected_resource_status)
            elif check_type == 'html_search':
                urls = check_data['urls']
                rules = check_data['rules']
                parser = check_data.get('parser', 'lxml')
                check = MarkupCheck(name, urls, rules, delay, alert_condition, output_options, base_url, parser)
            elif check_type == 'xml_search':
                urls = check_data['urls']
                rules = check_data['rules']
                parser = check_data.get('parser', 'lxml-xml')
                check = MarkupCheck(name, urls, rules, delay, alert_condition, output_options, base_url, parser)
            elif check_type == 'content_match':
                rules = check_data['rules']

                # If any of the URLs in a rule is a local file, the path is resolved
                # to the absolute path using the configuration file path
                rules = self.resolve_path_in_dict(rules)

                comparison_method = check_data.get('comparison_method', 'exact')
                check = ContentMatchCheck(name, rules, comparison_method, delay, alert_condition, output_options, base_url)
            else:
                continue

            checks.append(check)

        return checks



# Global reporter instance
reporter = Reporter()


# Main function to run the checks
if __name__ == "__main__":

    # Default configuration file name
    config_file = 'config.yaml'

    # See if a different configuration file was provided
    if len(sys.argv) > 1:
        config_file = sys.argv[1]
    
    config_handler = ConfigurationHandler(config_file)

    # Get the the output options
    output_options = config_handler.get_output_options()

    # Set the output options in the reporter
    reporter.set_output_options(output_options)

    # Starting message
    reporter.report_info(Scope.PROJECT, "SEO Sentinel v" + __version__ + " by " + __author__)

    # Get the project name and set it in the reporter
    project_name = config_handler.get_project_name()
    reporter.set_project_name(project_name)

    # Specify which config file is being used
    reporter.report_info(Scope.PROJECT, f"Using configuration file '{config_file}'.")

    # Parse the checks from the configuration file
    checks = config_handler.parse_checks()


    # Are there any checks to run? (check the length of the list)
    if len(checks) > 0:
        # Print the number of found checks
        reporter.report_info(Scope.PROJECT, f"Found {len(checks)} checks to run.")

        # Starting checks
        reporter.report_info(Scope.PROJECT, f"Starting checks for project '{project_name}'.")

        for check in checks:
            check.apply()
    else:
        reporter.report_warning(Scope.PROJECT, "No checks to run. Please review the configuration file.")




    # Response about the checks
    if reporter.check_failed:
        reporter.report_info(Scope.PROJECT, "Some checks failed. Please review the logs.")
    elif reporter.check_passed:
        reporter.report_info(Scope.PROJECT, "All project checks passed successfully.")

    # Response about the warnings
    if reporter.warning:
        reporter.report_info(Scope.PROJECT, "Some warnings were raised. Please review the logs.")

    # Ending message
    reporter.report_info(Scope.PROJECT, f"SEO Sentinel for project '{project_name}' finished.")