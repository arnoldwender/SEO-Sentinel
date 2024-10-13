# SEO Sentinel

**SEO Sentinel** is a simple but versatile Python utility designed to automate critical website checks, with a special focus on SEO analysis.

This software exists because it turns out that Content Management Systems, IT teams and website managers are not necessarily deterministic entities. Sometimes websites *just change or break unexpectedly*.


Search engines are quite sensitive to website problems and can react with reducing search visibility for long periods of time. **SEO Sentinel** tries to mitigate these problems by performing website checks and alerting the user if something looks unexpected.



## Features

* **Customizable Checks:** Users can create rules to search for specific patterns in HTML/XML tags or contents, monitor changes in files (e.g., robots.txt), and check for proper redirects.
* **Versatile Configuration:** The configuration file allows a variety of checks by specifying different parameters and conditions, making SEO Sentinel adaptable to multiple scenarios.
* **Alert and Logging System:** Choose how and where to get notified when a check fails (console, email, or log files).
* **Support for Delay and Status Settings:** Enable or disable specific checks and introduce delays between checks to avoid overloading the server.


### Dependencies

SEO Sentinel requires the following Python libraries:

- **PyYAML** (`yaml`) – For reading and writing YAML configuration files.
- **requests** – For making HTTP requests.
- **BeautifulSoup4** – For parsing HTML content.
- **lxml** – As the parser used by BeautifulSoup.

To install the necessary dependencies, run the following command:

```bash
pip install pyyaml requests beautifulsoup4 lxml
```


## Usage

Users need to create a **configuration file** in YAML format, specifying the details of the checks to be performed. Below is a breakdown of the configuration options available.

### General Structure

The configuration file is divided into two main sections:

1. **Checks**: Contains the list of checks to be performed.
    * A check contains a list of **Rules**. Each rule defines "something to look for" in a web resource and what is the expected outcome.
1. **Output**: Specifies how to report the results and how to warn the user.


### Check logic

You can design checks in two ways:
* Look for something **expected** and set `alert_condition` to `any is false` to get alerted if it’s missing.
* Look for something **unexpected** and set `alert_condition` to `any is true` to get alerted if it appears.


### Main check Configuration

Every check configuration usually includes the following **standard parameters**:

* **`name`**: The name of the check.
* **`type`**: Type of check to perform. Supported types include:
    * **`html_search`**: Searches the HTML of a resource for text in the content or the HTML tags.
    * **`xml_search`**: Similar to the html_search, but for XML resources like XML Sitemaps.
    * **`content_match`**: Compares the contents of two resources, which can be remote or local.
    * **`redirect`**: Verifies that specified redirects are working as expected.
* **`enabled`**: Can be set to `true` or `false` to control whether the check is active. Default is `true`.
* **`delay`**: Sets a delay (in seconds) between two URL requests.
* **`alert_condition`**: Specifies when an alert should be triggered. Options include `any is true` or `any is false`, depending on whether any rule should be considered met or unmet.
* **`rules`**: what exactly to look for in a URL. Its contents **depend on the type of check** (see below).

Checks can have additional parameters, depending on the type of check.


### Usage of `html_search` or `xml_search` checks

Besides the standard parameters of a check, `html_search` and `xml_search` include a parameter `urls` with the list of resources to check.

Each rule of these checks defines the specific search criteria and includes these parameters:

* **`name`**: The name of the rule.
* **`selector`**: CSS selector used to locate the elements on the page.
* **`attribute`**: An attribute to inspect (e.g., href).
* **`attribute_regex`** or **`attribute_literal`**: A pattern or literal value to match against the attribute's content. The value can contain the special string `{{checked_url}}`, which is replaced with the URL of the checked resource.
* **`count`**: Specifies the number of occurrences that should match the rule. This option supports:
    * A fixed number (e.g., "0").
    * A minimum number followed by a colon (e.g., "1:" for at least one instance).
    * A range of acceptable counts (e.g., "1:3" for between one and three instances).*


#### Example of a `html_search` check

The following code looks in each URL for two possible unexpected things and creates an alert if "any is true":
* typical non-canonical product URLs in links of a Shopify category page.
* the absence (`count = "0"`) of a "rel=canonical" URL that matches with the checked url. This rule uses the special string `{{checked_url}}` in the parameter `attribute_literal`.


```yaml
checks:
  - name: "Shopify canonicalization"
    type: "html_search"
    enabled: true # true, false. Default: true
    delay: 0
    alert_condition: "any is true"
    urls:
      - "https://example.com/collections/classics"
      - "https://example.com/collections/merch"
    rules:
      - name: "Non-canonical product URL in link"
        selector: "a[href]"
        attribute: "href"
        attribute_regex: ".*/collections/.+/products/.*"
        count: "1:"
      - name: "Canonical URL not matching checked URL"
        selector: "head link[rel='canonical']"
        attribute: "href"
        attribute_literal: "{{checked_url}}"
        count: "0"
```



### Usage of the `content_match` check

The `content_match` check will compare two resources, either remote ones or local ones.

Besides the standard parameters of a check, it also uses these parameters and rules:

- **`comparison_method`**: How the files are compared:
  - **`exact`**: Files must match exactly.
  - **`strip_whitespace`**: Ignores differences in whitespace.

- **`rules`**: Maps the online file URL to the local file path. The content of the URL is compared with the local file.

#### Example of a `content_match` check

Here is how a check of the contents of a robots.txt file might  look like:

```yaml
  - name: "Changed robots.txt"
    type: "content_match"
    enabled: true
    alert_condition: "any is false"
    comparison_method: "exact"
    rules:
      "https://example.com/robots.txt": "expected-robots.txt"
```


### Usage of the `redirect` check

The `redirect` check check will test if the requests of some URLs will result in receiving an HTTP redirect and an HTTP `Location` header which should contain the destination URL of the redirect.

Besides the standard parameters of a check, this check uses the following parameters and rules:

- **`base_url`**: The base URL to be prepended to the *source* paths in the `rules`.

- **`status_codes`**: The list of acceptable HTTP status codes for the redirects (e.g., `[301,302]` for both permanent and temporary redirects).

- **`rules`**: Defines the source and destination URLs for the redirects. The left side is the old path, and the right side is the new location.

- **`rules_csv`**: Specifies a CSV file that contains additional redirection rules. 
  - **`file`**: Path to the CSV file.
  - **`has_header`**: Indicates whether the CSV file has a header row (`true` or `false`).


#### Example of a `redirect` check

Here is how a check for the redirects of a migration to a Shopify website might look like:

```yaml
  - name: "Migration redirects"
    type: "redirect"
    enabled: true
    base_url: "https://example.com"
    delay: 0
    alert_condition: "any is false"
    status_codes: [301]
    rules:
      "/shirts.html": "/collections/shirts"
      "/colorful-hawaiian-shirt.html": "/products/hawaiian-shirt"
    rules_csv:
      file: "redirects.csv"
      has_header: true
```

### Usage of the `output` section

**Note**: The `email` and `file` output destinations are planned features and are not yet implemented in this version.

- **`timestamp`**: Controls whether timestamps are included in the output.
  - **`enabled`**: Set to `true` to include timestamps in the output, or `false` to exclude them.
  - **`format`**: Specifies the timestamp format using Python’s datetime formatting (e.g., `%Y-%m-%d %H-%M-%S %z`).
  - **`frequency`**: Determines how frequently the timestamp is logged:
    - `1`: Only at the project level.
    - `2`: At both the project and check levels.
    - `3`: For every single log row.

- **`destinations`**: Specifies where the output will be sent.

  - **`console`**: Controls output to the console (standard output).
    - **`enabled`**: Set to `true` to log output to the console.
    - **`log_level`**: Defines the verbosity of the logs:
      - **`all`**: Logs all information.
      - **`issues`**: Logs only issues (errors, warnings) and general information.

  - **`email`** (Not yet implemented): Controls output via email.
    - **`enabled`**: Set to `true` to enable email output (currently not functional).
    - **`send`**: When to send emails:
      - **`always`**: Send the email report after every run.
      - **`issues_only`**: Send the email only if issues are found.
    - **`recipients`**: List of email recipients.
    - **`subject`**: Subject of the email report, with placeholders like `{{project_name}}` for dynamic content.
    - **`attachment_log_level`**: Controls what is included in the email attachment:
      - **`all`**: Attach all logs.
      - **`issues`**: Attach only issues.

  - **`file`** (Not yet implemented): Controls output to a file.
    - **`enabled`**: Set to `true` to enable file logging.
    - **`log_level`**: What to log to the file:
      - **`all`**: Logs everything.
      - **`issues`**: Logs only issues and general information.
    - **`path`**: The path where the log file will be saved.
    - **`file_name`**: The name format of the log file, supporting placeholders like `{{timestamp}}` and `{{project_name}}`.
    - **`file_mode`**: Defines how the log file should be handled:
      - **`new_file`**: Creates a new file each time the script is run.
      - **`append`**: Appends to the existing log file.
      - **`overwrite`**: Overwrites the existing log file.


#### Example of the `output` section

```yaml
output:
  timestamp:
    enabled: true
    format: "%Y-%m-%d %H-%M-%S %z"
    frequency: 3

  destinations:
    console:
      enabled: true
      log_level: "issues"

    email:
      enabled: true
      send: "always"
      recipients:
        - "info@example.com"
      subject: "SEO Sentinel report for {{project_name}}"
      attachment_log_level: "all"

    file:
      enabled: true
      log_level: "all"
      path: "output.log"
      file_name: "{{timestamp}}-{{project_name}}.log"
      file_mode: "new_file"
```

## Changelog

### [v0.8.0] - 2024-10-13
- First version.


## License

SEO Sentinel is released under the MIT License.