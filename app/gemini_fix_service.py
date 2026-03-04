"""
app/gemini_fix_service.py
─────────────────────────────────────────────────────────────────────────────
Gemini-powered recommendation and fix suggestion generator.

Changes vs previous version:
  1. API key loaded from environment variable ONLY — no hardcoded fallback
  2. Graceful degradation if GEMINI_API_KEY is not set (returns static fix)
  3. Verbose error printing so you see EXACTLY why Gemini fails in server logs
  4. 'recommendation' field added to every FixSuggestion (static, always shown)
  5. Gemini prompt now produces recommendation + example fix + tips sections
  6. All static fallback data includes recommendation text
─────────────────────────────────────────────────────────────────────────────
"""
import os
import traceback
import requests as http_requests   

# ── Gemini API Config ──────────────────────────────────────────────────────
# Load from environment variable ONLY — never hardcode API keys in source code.
# Set this in your deployment platform's environment config (Railway, Render,
# Docker, etc.) or in a local .env file (which must be in .gitignore).
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

GEMINI_API_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "gemini-2.5-flash:generateContent"
)
GEMINI_TIMEOUT = 60   # seconds

# ── Static context per anti-pattern ───────────────────────────────────────
ANTI_PATTERN_CONTEXT = {
    "no_validation": {
        "impact_pts": -8,
        "layer": "Controller",
        "problem": (
            "Controller endpoints accept @RequestBody without @Valid annotation, "
            "allowing malformed or malicious data to reach business logic."
        ),
        "recommendation": (
            "Add @Valid annotation to all @RequestBody parameters to enable "
            "Bean Validation. Also annotate your DTO fields with constraints "
            "such as @NotNull, @NotBlank, @Size, and @Email."
        ),
        "before_stub": """\
@PostMapping("/users")
public ResponseEntity<User> createUser(@RequestBody UserRequest request) {
    return ResponseEntity.ok(userService.create(request));
}""",
        "after_stub": """\
@PostMapping("/users")
public ResponseEntity<User> createUser(@Valid @RequestBody UserRequest request) {
    return ResponseEntity.ok(userService.create(request));
}

// Global handler for validation errors:
@RestControllerAdvice
public class GlobalExceptionHandler {
    @ExceptionHandler(MethodArgumentNotValidException.class)
    public ResponseEntity<Map<String, String>> handleValidation(
            MethodArgumentNotValidException ex) {
        Map<String, String> errors = new HashMap<>();
        ex.getBindingResult().getFieldErrors()
          .forEach(e -> errors.put(e.getField(), e.getDefaultMessage()));
        return ResponseEntity.badRequest().body(errors);
    }
}"""
    },

    "business_logic_in_controller_layered": {
        "impact_pts": -12,
        "layer": "Controller",
        "problem": (
            "Business logic (conditionals, calculations, loops) is embedded in "
            "the Controller layer instead of the Service layer, violating the "
            "Single Responsibility Principle."
        ),
        "recommendation": (
            "Move all business logic into the Service layer. Controllers should "
            "only handle HTTP concerns: parse the request, call one service "
            "method, and return the response. Keep controllers under ~30 LOC."
        ),
        "before_stub": """\
@PostMapping("/orders")
public ResponseEntity<Order> createOrder(@RequestBody OrderRequest req) {
    // ❌ Business logic in Controller
    if (req.getItems().isEmpty()) throw new BadRequestException("Empty");
    double total = req.getItems().stream()
        .mapToDouble(i -> i.getPrice() * i.getQty()).sum();
    return ResponseEntity.ok(orderRepository.save(new Order(req, total)));
}""",
        "after_stub": """\
// ✅ Controller — thin, delegates entirely
@PostMapping("/orders")
public ResponseEntity<Order> createOrder(@Valid @RequestBody OrderRequest req) {
    return ResponseEntity.ok(orderService.createOrder(req));
}

// ✅ Service — owns all business logic + @Transactional
@Service
public class OrderService {
    @Transactional
    public Order createOrder(OrderRequest req) {
        if (req.getItems().isEmpty()) throw new BadRequestException("Empty");
        double total = req.getItems().stream()
            .mapToDouble(i -> i.getPrice() * i.getQty()).sum();
        return orderRepository.save(new Order(req, total));
    }
}"""
    },

    "layer_skip_in_layered": {
        "impact_pts": -15,
        "layer": "Controller",
        "problem": (
            "Controller directly injects and uses a Repository, bypassing the "
            "Service layer. This breaks layered architecture and leaks "
            "data-access concerns into the web layer."
        ),
        "recommendation": (
            "Remove the Repository injection from the Controller. Create a "
            "Service class that wraps the Repository operations, then inject "
            "only the Service into the Controller."
        ),
        "before_stub": """\
@RestController
public class UserController {
    @Autowired
    private UserRepository userRepository; // ❌ skips Service layer

    @GetMapping("/users/{id}")
    public User getUser(@PathVariable Long id) {
        return userRepository.findById(id).orElseThrow();
    }
}""",
        "after_stub": """\
// ✅ Controller — depends only on Service
@RestController @RequiredArgsConstructor
public class UserController {
    private final UserService userService;

    @GetMapping("/users/{id}")
    public User getUser(@PathVariable Long id) {
        return userService.findById(id);
    }
}

// ✅ Service — mediates between Controller and Repository
@Service @RequiredArgsConstructor
public class UserService {
    private final UserRepository userRepository;

    public User findById(Long id) {
        return userRepository.findById(id)
            .orElseThrow(() -> new ResourceNotFoundException("User " + id));
    }
}"""
    },

    "missing_transaction_in_layered": {
        "impact_pts": -10,
        "layer": "Service",
        "problem": (
            "Service methods that write to the database are missing "
            "@Transactional, risking partial writes and data inconsistency "
            "when an exception occurs mid-operation."
        ),
        "recommendation": (
            "Annotate all data-modifying Service methods with @Transactional. "
            "Use @Transactional(readOnly = true) on read-only methods for "
            "a performance benefit. Place the annotation on concrete class "
            "methods, not on interface methods."
        ),
        "before_stub": """\
@Service
public class OrderService {
    // ❌ No @Transactional — partial writes possible
    public Order createOrder(OrderRequest req) {
        Order o = orderRepository.save(new Order(req));
        inventoryRepository.deduct(req.getItems()); // fails? order already saved!
        return o;
    }
}""",
        "after_stub": """\
@Service
public class OrderService {
    @Transactional  // ✅ atomic — both saves roll back together on error
    public Order createOrder(OrderRequest req) {
        Order o = orderRepository.save(new Order(req));
        inventoryRepository.deduct(req.getItems());
        return o;
    }

    @Transactional(readOnly = true)  // ✅ read-only hint for performance
    public List<Order> findByUser(Long userId) {
        return orderRepository.findByUserId(userId);
    }
}"""
    },

    "missing_port_adapter_in_hexagonal": {
        "impact_pts": -20,
        "layer": "Service",
        "problem": (
            "Domain/Service layer directly references the Spring Data Repository "
            "(infrastructure), breaking the Hexagonal boundary. The domain "
            "should depend only on a Port interface."
        ),
        "recommendation": (
            "Create a Port interface in the domain package. Implement that Port "
            "with an Adapter class in the infrastructure package that wraps the "
            "Spring Data Repository. Inject the Port (not the Adapter) into "
            "your domain service."
        ),
        "before_stub": """\
@Service
public class OrderDomainService {
    @Autowired
    private OrderRepository orderRepository; // ❌ infrastructure in domain!

    public Order placeOrder(OrderRequest req) {
        return orderRepository.save(new Order(req));
    }
}""",
        "after_stub": """\
// ✅ Port — in domain package (pure Java interface)
public interface OrderPort {
    Order save(Order order);
    Optional<Order> findById(Long id);
}

// ✅ Domain Service — depends only on the Port interface
@Service @RequiredArgsConstructor
public class OrderDomainService {
    private final OrderPort orderPort;

    public Order placeOrder(OrderRequest req) {
        return orderPort.save(new Order(req));
    }
}

// ✅ Adapter — in infrastructure package, implements the Port
@Component @RequiredArgsConstructor
public class OrderRepositoryAdapter implements OrderPort {
    private final OrderJpaRepository jpaRepository;
    @Override public Order save(Order o)                { return jpaRepository.save(o); }
    @Override public Optional<Order> findById(Long id)  { return jpaRepository.findById(id); }
}"""
    },

    "framework_dependency_in_domain_hexagonal": {
        "impact_pts": -18,
        "layer": "Service",
        "problem": (
            "Domain/Service class imports Spring or JPA framework annotations, "
            "coupling the domain core to infrastructure details and violating "
            "Hexagonal Architecture's dependency rule."
        ),
        "recommendation": (
            "Remove all framework annotations (@Service, @Entity, @Autowired, "
            "@Column, etc.) from domain classes. Keep domain classes as plain "
            "Java objects. Move JPA persistence to separate entity classes in "
            "the infrastructure/adapter layer."
        ),
        "before_stub": """\
import org.springframework.stereotype.Service; // ❌ framework in domain
import javax.persistence.Entity;               // ❌ JPA in domain

@Service @Entity
public class Order { /* ... */ }""",
        "after_stub": """\
// ✅ Pure domain class — zero framework imports
public class Order {
    private Long id;
    private String userId;
    private double total;
    // only domain logic here — no annotations
}

// ✅ JPA entity stays in infrastructure layer only
@Entity @Table(name = "orders")
class OrderEntity {
    @Id @GeneratedValue private Long id;
    private String userId;
    private double total;
    static OrderEntity from(Order o) { /* map fields */ }
    Order toDomain()                 { /* map fields */ }
}"""
    },

    "tight_coupling_new_keyword": {
        "impact_pts": -7,
        "layer": "Service / Controller",
        "problem": (
            "Dependencies are instantiated with 'new' instead of being injected, "
            "preventing testability, making the code impossible to mock, "
            "and hiding the class's real dependencies."
        ),
        "recommendation": (
            "Replace 'new' instantiation with constructor injection. Declare "
            "dependencies as final fields and let Spring manage object creation. "
            "This makes unit testing straightforward with @Mock / @InjectMocks."
        ),
        "before_stub": """\
@Service
public class NotificationService {
    // ❌ hard-coded — impossible to mock in unit tests
    private EmailClient emailClient = new EmailClient();
    private SmsClient   smsClient   = new SmsClient();
}""",
        "after_stub": """\
@Service @RequiredArgsConstructor
public class NotificationService {
    private final EmailClient emailClient;  // ✅ injected by Spring
    private final SmsClient   smsClient;

    // Unit test becomes simple:
    // @Mock EmailClient emailClient;
    // @InjectMocks NotificationService service;
}"""
    },

    "broad_catch": {
        "impact_pts": -6,
        "layer": "Any",
        "problem": (
            "Catching generic Exception or Throwable swallows unexpected errors "
            "silently, making debugging extremely difficult and hiding real "
            "failures from monitoring tools."
        ),
        "recommendation": (
            "Catch only specific, expected exception types. Let unexpected "
            "exceptions propagate to a global @ControllerAdvice handler. "
            "Always log the full stack trace before re-throwing or wrapping."
        ),
        "before_stub": """\
try {
    userService.deleteUser(id);
} catch (Exception e) { // ❌ catches NPE, OOM, everything
    log.error("Error", e);
}""",
        "after_stub": """\
try {
    userService.deleteUser(id);
} catch (UserNotFoundException e) {
    throw new ResponseStatusException(HttpStatus.NOT_FOUND, e.getMessage(), e);
} catch (DataIntegrityViolationException e) {
    throw new ResponseStatusException(HttpStatus.CONFLICT,
        "User has related data and cannot be deleted", e);
}
// Unexpected exceptions propagate to @ControllerAdvice — handled globally"""
    },

    "clean": {
        "impact_pts": 0,
        "layer": "N/A",
        "problem": "No anti-patterns detected.",
        "recommendation": "No action required. Code follows architectural best practices.",
        "before_stub": "",
        "after_stub": ""
    }
}


# ── Gemini API caller ──────────────────────────────────────────────────────

def _call_gemini(prompt: str) -> str:
    """
    Call Gemini and return the generated text.
    Returns "" if API key is not configured or on any failure.
    Prints diagnostic info to the uvicorn server console.
    """
    if not GEMINI_API_KEY:
        print("  [Gemini] Skipped — GEMINI_API_KEY environment variable is not set.")
        return ""

    try:
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature":     0.3,
                "maxOutputTokens": 2048,
                "topP":            0.8,
            }
        }
        resp = http_requests.post(
            f"{GEMINI_API_URL}?key={GEMINI_API_KEY}",
            json=payload,
            timeout=GEMINI_TIMEOUT,
        )

        print(f"  [Gemini] HTTP status: {resp.status_code}")

        if resp.status_code != 200:
            print(f"  [Gemini] Error body: {resp.text[:600]}")
            return ""

        data = resp.json()
        candidates = data.get("candidates", [])
        if not candidates:
            print(f"  [Gemini] No candidates in response: {data}")
            return ""

        parts = candidates[0].get("content", {}).get("parts", [])
        if not parts:
            print(f"  [Gemini] No parts in first candidate")
            return ""

        text = parts[0].get("text", "").strip()
        if not text:
            print(f"  [Gemini] Empty text part returned")
            return ""

        print(f"  [Gemini] Success — {len(text)} chars")
        return text

    except Exception:
        print(f"  [Gemini] Exception during API call:")
        traceback.print_exc()
        return ""


# ── Prompt builder ─────────────────────────────────────────────────────────

def build_gemini_prompt(
    anti_pattern: str,
    files:        list,
    architecture: str,
    layer:        str,
    severity:     str,
    description:  str,
) -> str:
    ctx    = ANTI_PATTERN_CONTEXT.get(anti_pattern, {})
    before = ctx.get("before_stub", "")
    after  = ctx.get("after_stub",  "")

    file_list = "\n".join(f"  - {f}" for f in files[:5])
    if len(files) > 5:
        file_list += f"\n  - ... and {len(files) - 5} more files"

    seed = ""
    if before and after:
        seed = f"""
Reference example (adapt for the specific files listed above):
// ❌ BEFORE
{before}

// ✅ AFTER
{after}
"""

    return f"""You are a senior Spring Boot architect reviewing a code quality report.

Anti-pattern: {anti_pattern.replace("_", " ").title()}
Architecture: {architecture}
Affected layer: {layer}
Severity: {severity}
Files affected:
{file_list}
Problem: {description}
{seed}
Write a concise fix suggestion using EXACTLY this format (no preamble, no conclusion):

💡 RECOMMENDATION:
<2 clear sentences about what to change in the specific files listed above>

🔧 EXAMPLE FIX:
// ❌ BEFORE
<short problematic code snippet>

// ✅ AFTER
<short corrected code snippet>

⭐ EXTRA TIPS:
• <Spring Boot best-practice tip 1>
• <Spring Boot best-practice tip 2>"""


# ── Main public API ────────────────────────────────────────────────────────

def generate_fix_suggestion(
    anti_pattern: str,
    files:        list,
    architecture: str,
    layer:        str,
    severity:     str,
    description:  str,
    use_gemini:   bool = True,
) -> dict:
    """
    Build a complete fix suggestion dict.
    Static fields (recommendation, before/after code) are ALWAYS present.
    gemini_fix is added when Gemini responds successfully.
    If GEMINI_API_KEY is not set, degrades gracefully to static fix only.
    """
    ctx = ANTI_PATTERN_CONTEXT.get(anti_pattern, ANTI_PATTERN_CONTEXT["clean"])

    result = {
        "anti_pattern":   anti_pattern,
        "layer":          layer or ctx.get("layer", ""),
        "severity":       severity,
        "impact_points":  ctx.get("impact_pts", 0),
        "problem":        description or ctx.get("problem", ""),
        "recommendation": ctx.get("recommendation", ""),
        "files":          files,
        "before_code":    ctx.get("before_stub", ""),
        "after_code":     ctx.get("after_stub", ""),
        "gemini_fix":     "",
        "ai_powered":     False,
    }

    if not use_gemini or anti_pattern == "clean":
        return result

    print(f"\n  → Calling Gemini for '{anti_pattern}' ({len(files)} files)...")
    gemini_text = _call_gemini(
        build_gemini_prompt(
            anti_pattern=anti_pattern,
            files=files,
            architecture=architecture,
            layer=layer or ctx.get("layer", ""),
            severity=severity,
            description=description or ctx.get("problem", ""),
        )
    )

    if gemini_text:
        result["gemini_fix"] = gemini_text
        result["ai_powered"] = True

    return result


def generate_project_fixes(anti_patterns: list, architecture: str) -> list:
    """Generate fix suggestions for every anti-pattern in a project."""
    suggestions = []
    for ap in anti_patterns:
        ap_type = ap.get("type", "")
        if ap_type == "clean":
            continue
        suggestions.append(generate_fix_suggestion(
            anti_pattern=ap_type,
            files=ap.get("files", []),
            architecture=architecture,
            layer=ap.get("affected_layer", ""),
            severity=ap.get("severity", ""),
            description=ap.get("description", ""),
            use_gemini=True,
        ))
    return suggestions