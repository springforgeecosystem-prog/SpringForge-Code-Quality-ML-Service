"""
app/gemini_fix_service.py  — v3
──────────────────────────────────────────────────────────────────
FIXES FROM v2:
  1. Model name changed from gemini-2.0-flash to gemini-2.5-flash
     (2.5-flash is unreleased/preview — causes silent 404 failures)
     Override via GEMINI_MODEL env variable if needed.

  2. generate_project_fixes() now runs Gemini calls in PARALLEL
     using ThreadPoolExecutor (max 5 workers).
     Old: 8 violations * 15s = 120s total
     New: 8 violations / 5 workers = ~30s total

  3. Human-readable anti-pattern display names added.
     Old: "Missing Transaction In Layered" (ugly title-case)
     New: "Missing @Transactional in Service Layer" (clear)

  4. Gemini HTTP error reason now logged clearly (400/403/404
     all print the exact error body for easier debugging).

  5. generate_project_fixes() guards against unknown pattern names
     — logs a warning instead of silently returning empty fix data.

  6. test_recommendation_field_always_present() in test file now
     sends correct architecture per pattern (not always "layered").
──────────────────────────────────────────────────────────────────
"""
import os
import traceback
import requests as http_requests
from concurrent.futures import ThreadPoolExecutor, as_completed

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# FIX 1: Use gemini-2.5-flash as default — stable and available.
# Override with GEMINI_MODEL env variable if you want a different model.
_DEFAULT_MODEL  = "gemini-2.5-flash"
GEMINI_MODEL    = os.getenv("GEMINI_MODEL", _DEFAULT_MODEL)
GEMINI_API_URL  = (
    f"https://generativelanguage.googleapis.com/v1beta/models/"
    f"{GEMINI_MODEL}:generateContent"
)
GEMINI_TIMEOUT  = 45   # reduced from 60 — fail fast, use static fallback

# FIX 3: Human-readable display names for the Gemini prompt
DISPLAY_NAMES = {
    "no_validation"                          : "Missing Input Validation (@Valid)",
    "business_logic_in_controller_layered"   : "Business Logic in Controller Layer",
    "layer_skip_in_layered"                  : "Layer Skip (Controller→Repository)",
    "reversed_dependency_in_layered"         : "Reversed Dependency (Service→Controller)",
    "missing_transaction_in_layered"         : "Missing @Transactional in Service Layer",
    "missing_port_adapter_in_hexagonal"      : "Missing Port/Adapter (Infrastructure in Domain)",
    "framework_dependency_in_domain_hexagonal": "Framework Dependency in Domain Layer",
    "adapter_without_port_hexagonal"         : "Adapter Without Port Interface",
    "outer_depends_on_inner_clean"           : "Outer Layer Depends on Inner Layer",
    "usecase_framework_coupling_clean"       : "Use Case Coupled with Framework",
    "entity_framework_coupling_clean"        : "Domain Entity Has JPA Annotations",
    "missing_gateway_interface_clean"        : "Use Case Accesses Repository Directly",
    "tight_coupling_new_keyword"             : "Tight Coupling (Using 'new' Keyword)",
    "broad_catch"                            : "Broad Exception Catch (Exception/Throwable)",
    "clean"                                  : "Clean — No Anti-Pattern",
}

# ── Static context per anti-pattern ───────────────────────────────────────
ANTI_PATTERN_CONTEXT = {

    # ── LAYERED / MVC ────────────────────────────────────────────────────
    "no_validation": {
        "impact_pts": -8, "layer": "Controller",
        "problem": "Controller endpoints accept @RequestBody without @Valid, allowing malformed data to reach business logic.",
        "recommendation": "Add @Valid to all @RequestBody parameters. Annotate DTO fields with @NotNull, @NotBlank, @Size, @Email.",
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
@RestControllerAdvice
public class GlobalExceptionHandler {
    @ExceptionHandler(MethodArgumentNotValidException.class)
    public ResponseEntity<Map<String, String>> handleValidation(MethodArgumentNotValidException ex) {
        Map<String, String> errors = new HashMap<>();
        ex.getBindingResult().getFieldErrors()
          .forEach(e -> errors.put(e.getField(), e.getDefaultMessage()));
        return ResponseEntity.badRequest().body(errors);
    }
}"""
    },

    "business_logic_in_controller_layered": {
        "impact_pts": -12, "layer": "Controller",
        "problem": "Business logic (conditionals, loops, calculations) is embedded in the Controller instead of the Service layer.",
        "recommendation": "Move all business logic to the Service layer. Controllers should only parse requests, call one Service method, and return the response.",
        "before_stub": """\
@PostMapping("/orders")
public ResponseEntity<Order> createOrder(@RequestBody OrderRequest req) {
    if (req.getItems().isEmpty()) throw new BadRequestException("Empty");
    double total = req.getItems().stream().mapToDouble(i -> i.getPrice() * i.getQty()).sum();
    return ResponseEntity.ok(orderRepository.save(new Order(req, total)));
}""",
        "after_stub": """\
@PostMapping("/orders")
public ResponseEntity<Order> createOrder(@Valid @RequestBody OrderRequest req) {
    return ResponseEntity.ok(orderService.createOrder(req));
}
@Service
public class OrderService {
    @Transactional
    public Order createOrder(OrderRequest req) {
        if (req.getItems().isEmpty()) throw new BadRequestException("Empty");
        double total = req.getItems().stream().mapToDouble(i -> i.getPrice() * i.getQty()).sum();
        return orderRepository.save(new Order(req, total));
    }
}"""
    },

    "layer_skip_in_layered": {
        "impact_pts": -15, "layer": "Controller",
        "problem": "Controller directly injects and uses a Repository, bypassing the Service layer.",
        "recommendation": "Remove Repository injection from Controller. Create a Service class wrapping Repository operations and inject only the Service.",
        "before_stub": """\
@RestController
public class UserController {
    @Autowired private UserRepository userRepository; // ❌ skips Service
    @GetMapping("/users/{id}")
    public User getUser(@PathVariable Long id) {
        return userRepository.findById(id).orElseThrow();
    }
}""",
        "after_stub": """\
@RestController @RequiredArgsConstructor
public class UserController {
    private final UserService userService;
    @GetMapping("/users/{id}")
    public User getUser(@PathVariable Long id) { return userService.findById(id); }
}
@Service @RequiredArgsConstructor
public class UserService {
    private final UserRepository userRepository;
    public User findById(Long id) {
        return userRepository.findById(id)
            .orElseThrow(() -> new ResourceNotFoundException("User " + id));
    }
}"""
    },

    "reversed_dependency_in_layered": {
        "impact_pts": -15, "layer": "Service",
        "problem": "Service layer injects a Controller, creating a reversed dependency that violates layered architecture.",
        "recommendation": "Remove all Controller imports and dependencies from Service classes. Use ApplicationEventPublisher if cross-layer notification is needed.",
        "before_stub": """\
@Service
public class OrderService {
    @Autowired
    private OrderController orderController; // ❌ reversed dependency
}""",
        "after_stub": """\
@Service @RequiredArgsConstructor
public class OrderService {
    private final OrderRepository orderRepository;
    private final ApplicationEventPublisher eventPublisher;
    public void processOrder(Order o) {
        orderRepository.save(o);
        eventPublisher.publishEvent(new OrderProcessedEvent(o));
    }
}"""
    },

    "missing_transaction_in_layered": {
        "impact_pts": -10, "layer": "Service",
        "problem": "Service methods write to the database without @Transactional, risking partial writes and data inconsistency.",
        "recommendation": "Add @Transactional to all data-modifying Service methods. Use @Transactional(readOnly=true) on read-only methods.",
        "before_stub": """\
@Service
public class OrderService {
    public Order createOrder(OrderRequest req) {  // ❌ no @Transactional
        Order o = orderRepository.save(new Order(req));
        inventoryRepository.deduct(req.getItems());
        return o;
    }
}""",
        "after_stub": """\
@Service
public class OrderService {
    @Transactional
    public Order createOrder(OrderRequest req) {  // ✅ atomic
        Order o = orderRepository.save(new Order(req));
        inventoryRepository.deduct(req.getItems());
        return o;
    }
    @Transactional(readOnly = true)
    public List<Order> findByUser(Long userId) {
        return orderRepository.findByUserId(userId);
    }
}"""
    },

    # ── HEXAGONAL ────────────────────────────────────────────────────────
    "missing_port_adapter_in_hexagonal": {
        "impact_pts": -20, "layer": "Service",
        "problem": "Domain/Service layer directly references Spring Data Repository (infrastructure), breaking the Hexagonal boundary.",
        "recommendation": "Create a Port interface in the domain package. Implement it with an Adapter in the infrastructure package. Inject the Port into the domain service.",
        "before_stub": """\
@Service
public class OrderDomainService {
    @Autowired
    private OrderRepository orderRepository; // ❌ infrastructure in domain
    public Order placeOrder(OrderRequest req) {
        return orderRepository.save(new Order(req));
    }
}""",
        "after_stub": """\
// Port — pure Java interface in domain package
public interface OrderPort {
    Order save(Order order);
    Optional<Order> findById(Long id);
}
// Domain Service — depends only on Port
@Service @RequiredArgsConstructor
public class OrderDomainService {
    private final OrderPort orderPort;
    public Order placeOrder(OrderRequest req) { return orderPort.save(new Order(req)); }
}
// Adapter — in infrastructure package
@Component @RequiredArgsConstructor
public class OrderRepositoryAdapter implements OrderPort {
    private final OrderJpaRepository jpaRepository;
    @Override public Order save(Order o) { return jpaRepository.save(o); }
    @Override public Optional<Order> findById(Long id) { return jpaRepository.findById(id); }
}"""
    },

    "framework_dependency_in_domain_hexagonal": {
        "impact_pts": -18, "layer": "Service",
        "problem": "Domain/Service class imports Spring or JPA annotations, violating the Hexagonal dependency rule.",
        "recommendation": "Remove all framework annotations (@Service, @Entity, @Autowired) from domain classes. Keep domain classes as plain Java objects.",
        "before_stub": """\
import org.springframework.stereotype.Service; // ❌ framework in domain
import javax.persistence.Entity;               // ❌ JPA in domain
@Service @Entity
public class Order { ... }""",
        "after_stub": """\
// Pure domain class — zero framework imports
public class Order {
    private Long id;
    private String userId;
    private double total;
}
// JPA entity stays in infrastructure layer only
@Entity @Table(name = "orders")
class OrderJpaEntity {
    @Id @GeneratedValue private Long id;
    private String userId;
    private double total;
    static OrderJpaEntity from(Order o) { /* map */ }
    Order toDomain()                    { /* map */ }
}"""
    },

    "adapter_without_port_hexagonal": {
        "impact_pts": -10, "layer": "Adapter",
        "problem": "Adapter class does not implement a Port interface, breaking the hexagonal contract.",
        "recommendation": "Create a Port interface in the domain package and make the Adapter implement it.",
        "before_stub": """\
@Component
public class UserRepositoryAdapter {   // ❌ implements nothing
    private final UserJpaRepository jpa;
    public User findById(Long id) { return jpa.findById(id).map(this::toDomain).orElseThrow(); }
}""",
        "after_stub": """\
// Port in domain package
public interface UserPort {
    User findById(Long id);
    User save(User user);
}
// Adapter implements Port
@Component @RequiredArgsConstructor
public class UserRepositoryAdapter implements UserPort {
    private final UserJpaRepository jpa;
    @Override public User findById(Long id) { return jpa.findById(id).map(this::toDomain).orElseThrow(); }
    @Override public User save(User user)   { return toDomain(jpa.save(toEntity(user))); }
}"""
    },

    # ── CLEAN ARCHITECTURE ───────────────────────────────────────────────
    "outer_depends_on_inner_clean": {
        "impact_pts": -20, "layer": "Controller",
        "problem": "Outer layer (Controller) directly depends on inner layer details (Entity or Repository), violating the Dependency Rule.",
        "recommendation": "Controllers should depend only on Use Case input/output ports. Use DTOs to cross layer boundaries, never domain Entities.",
        "before_stub": """\
@RestController
public class UserController {
    @Autowired private UserRepository userRepository; // ❌ inner layer in outer
    @GetMapping("/users/{id}")
    public User getUser(@PathVariable Long id) {
        return userRepository.findById(id).orElseThrow();
    }
}""",
        "after_stub": """\
// Use Case interface (input port) in application layer
public interface GetUserUseCase {
    UserResponseDTO execute(Long userId);
}
// Controller depends only on the Use Case interface
@RestController @RequiredArgsConstructor
public class UserController {
    private final GetUserUseCase getUserUseCase;
    @GetMapping("/users/{id}")
    public UserResponseDTO getUser(@PathVariable Long id) {
        return getUserUseCase.execute(id);
    }
}"""
    },

    "usecase_framework_coupling_clean": {
        "impact_pts": -18, "layer": "Service",
        "problem": "Use Case layer is coupled with Spring/JPA framework annotations, making it framework-dependent.",
        "recommendation": "Remove all framework annotations from Use Case classes. Use Cases should be plain Java classes with no Spring or JPA imports.",
        "before_stub": """\
import org.springframework.stereotype.Service; // ❌ framework in use case
@Service
public class CreateOrderUseCase {
    @Autowired private OrderJpaRepository repo; // ❌ JPA in use case
    public Order execute(CreateOrderInput input) { ... }
}""",
        "after_stub": """\
// Use Case — plain Java, no framework imports
public class CreateOrderUseCase {
    private final OrderGateway orderGateway;
    public CreateOrderUseCase(OrderGateway orderGateway) {
        this.orderGateway = orderGateway;
    }
    public CreateOrderOutput execute(CreateOrderInput input) {
        return new CreateOrderOutput(orderGateway.save(new Order(input.getUserId())));
    }
}
// Gateway interface — defined in Use Case layer
public interface OrderGateway { Order save(Order order); }
// Gateway implementation — in Infrastructure layer
@Repository
public class OrderGatewayImpl implements OrderGateway {
    private final OrderJpaRepository jpa;
    @Override public Order save(Order o) { return jpa.save(OrderEntity.from(o)).toDomain(); }
}"""
    },

    "entity_framework_coupling_clean": {
        "impact_pts": -12, "layer": "Entity",
        "problem": "Domain Entity has JPA annotations (@Entity, @Table, @Column), coupling the domain model to the persistence framework.",
        "recommendation": "Separate domain entities (pure Java) from JPA persistence entities. Keep @Entity classes only in the infrastructure layer.",
        "before_stub": """\
@Entity @Table(name = "orders")          // ❌ JPA in domain entity
public class Order {
    @Id @GeneratedValue private Long id;
    @Column(name = "user_id") private String userId;
    private double total;
}""",
        "after_stub": """\
// Domain Entity — pure Java, no JPA
public class Order {
    private final String userId;
    private final double total;
    public Order(String userId, double total) { this.userId = userId; this.total = total; }
}
// JPA Entity — ONLY in infrastructure package
@Entity @Table(name = "orders")
class OrderJpaEntity {
    @Id @GeneratedValue private Long id;
    @Column(name = "user_id") private String userId;
    private double total;
    Order toDomain() { return new Order(userId, total); }
    static OrderJpaEntity from(Order o) {
        OrderJpaEntity e = new OrderJpaEntity();
        e.userId = o.getUserId(); e.total = o.getTotal();
        return e;
    }
}"""
    },

    "missing_gateway_interface_clean": {
        "impact_pts": -15, "layer": "Service",
        "problem": "Use Case accesses Repository directly without a Gateway interface, violating the Dependency Rule.",
        "recommendation": "Create a Gateway interface in the Use Case layer. Implement it in infrastructure. The Use Case depends only on the interface.",
        "before_stub": """\
public class GetProductsUseCase {
    private final ProductJpaRepository repo; // ❌ Use Case depends on infrastructure
    public List<Product> execute() {
        return repo.findAll().stream().map(this::toDomain).collect(toList());
    }
}""",
        "after_stub": """\
// Gateway interface — in Use Case / application layer
public interface ProductGateway {
    List<Product> findAll();
    Optional<Product> findById(Long id);
}
// Use Case — depends only on the Gateway interface
public class GetProductsUseCase {
    private final ProductGateway productGateway;
    public GetProductsUseCase(ProductGateway productGateway) {
        this.productGateway = productGateway;
    }
    public List<Product> execute() { return productGateway.findAll(); }
}
// Gateway implementation — in Infrastructure layer
@Repository @RequiredArgsConstructor
public class ProductGatewayImpl implements ProductGateway {
    private final ProductJpaRepository jpa;
    @Override public List<Product> findAll() {
        return jpa.findAll().stream().map(ProductJpaEntity::toDomain).collect(toList());
    }
}"""
    },

    # ── COMMON ───────────────────────────────────────────────────────────
    "tight_coupling_new_keyword": {
        "impact_pts": -7, "layer": "Service / Controller",
        "problem": "Dependencies instantiated with 'new' instead of injection, preventing testability and hiding real dependencies.",
        "recommendation": "Replace 'new' instantiation with constructor injection. Declare dependencies as final fields and let Spring manage creation.",
        "before_stub": """\
@Service
public class NotificationService {
    private EmailClient emailClient = new EmailClient(); // ❌ hard-coded
    private SmsClient   smsClient   = new SmsClient();   // ❌ impossible to mock
}""",
        "after_stub": """\
@Service @RequiredArgsConstructor
public class NotificationService {
    private final EmailClient emailClient; // ✅ injected by Spring
    private final SmsClient   smsClient;
}"""
    },

    "broad_catch": {
        "impact_pts": -6, "layer": "Any",
        "problem": "Catching generic Exception or Throwable swallows unexpected errors, making debugging very difficult.",
        "recommendation": "Catch only specific, expected exception types. Let unexpected exceptions propagate to a global @ControllerAdvice.",
        "before_stub": """\
try {
    userService.deleteUser(id);
} catch (Exception e) { // ❌ catches everything
    log.error("Error", e);
}""",
        "after_stub": """\
try {
    userService.deleteUser(id);
} catch (UserNotFoundException e) {
    throw new ResponseStatusException(HttpStatus.NOT_FOUND, e.getMessage(), e);
} catch (DataIntegrityViolationException e) {
    throw new ResponseStatusException(HttpStatus.CONFLICT, "User has related data", e);
}
// Unexpected exceptions propagate to @ControllerAdvice"""
    },

    "clean": {
        "impact_pts": 0, "layer": "N/A",
        "problem": "No anti-patterns detected.",
        "recommendation": "No action required. Code follows architectural best practices.",
        "before_stub": "",
        "after_stub": ""
    },
}


# ── Gemini API caller ──────────────────────────────────────────────────────
def _call_gemini(prompt: str) -> str:
    """Call Gemini API. Returns empty string on any failure."""
    
    # ── DETAILED DIAGNOSTICS ──────────────────────────────────────
    print(f"\n  [Gemini] ── _call_gemini() called ──")
    print(f"  [Gemini] API key set  : {bool(GEMINI_API_KEY)}")
    print(f"  [Gemini] Key prefix   : {GEMINI_API_KEY[:8] if GEMINI_API_KEY else 'NONE'}...")
    print(f"  [Gemini] Model        : {GEMINI_MODEL}")
    print(f"  [Gemini] URL          : {GEMINI_API_URL}")
    print(f"  [Gemini] Prompt chars : {len(prompt)}")
    # ─────────────────────────────────────────────────────────────

    if not GEMINI_API_KEY:
        print("  [Gemini] ❌ Skipped — GEMINI_API_KEY not set.")
        return ""
    try:
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.3,
                "maxOutputTokens": 2048,
                "topP": 0.8,
            },
        }
        print(f"  [Gemini] Sending POST request (timeout={GEMINI_TIMEOUT}s)...")
        resp = http_requests.post(
            f"{GEMINI_API_URL}?key={GEMINI_API_KEY}",
            json=payload,
            timeout=GEMINI_TIMEOUT,
        )
        print(f"  [Gemini] HTTP {resp.status_code}  model={GEMINI_MODEL}")

        if resp.status_code != 200:
            print(f"  [Gemini] ❌ Error body: {resp.text[:600]}")
            return ""

        data       = resp.json()
        candidates = data.get("candidates", [])
        print(f"  [Gemini] Candidates returned: {len(candidates)}")
        
        if not candidates:
            print(f"  [Gemini] ❌ No candidates — full response: {str(data)[:400]}")
            return ""

        # Check for content filtering block
        finish_reason = candidates[0].get("finishReason", "")
        print(f"  [Gemini] Finish reason: {finish_reason}")
        if finish_reason in ("SAFETY", "RECITATION", "BLOCKED"):
            print(f"  [Gemini] ❌ Blocked by content filter: {finish_reason}")
            return ""

        parts = candidates[0].get("content", {}).get("parts", [])
        print(f"  [Gemini] Parts in response: {len(parts)}")
        
        text = parts[0].get("text", "").strip() if parts else ""
        print(f"  [Gemini] ✅ OK — {len(text)} chars returned")
        return text

    except http_requests.exceptions.Timeout:
        print(f"  [Gemini] ❌ Timeout after {GEMINI_TIMEOUT}s — using static fallback")
        return ""
    except http_requests.exceptions.ConnectionError as e:
        print(f"  [Gemini] ❌ Connection error: {e}")
        return ""
    except Exception:
        print("  [Gemini] ❌ Unexpected exception:")
        traceback.print_exc()
        return ""


def _display_name(anti_pattern: str) -> str:
    """FIX 3: Return a clean display name for the anti-pattern."""
    return DISPLAY_NAMES.get(anti_pattern, anti_pattern.replace("_", " ").title())


def build_gemini_prompt(anti_pattern, files, architecture, layer, severity, description):
    ctx       = ANTI_PATTERN_CONTEXT.get(anti_pattern, {})
    before    = ctx.get("before_stub", "")
    after     = ctx.get("after_stub",  "")
    name      = _display_name(anti_pattern)   # FIX 3
    file_list = "\n".join(f"  - {f}" for f in files[:5])
    if len(files) > 5:
        file_list += f"\n  - ... and {len(files) - 5} more files"

    seed = ""
    if before and after:
        seed = (
            f"\nReference example (adapt for the files listed above):\n"
            f"// ❌ BEFORE\n{before}\n// ✅ AFTER\n{after}\n"
        )

    return f"""You are a senior Spring Boot architect reviewing a {architecture} architecture project.

Anti-pattern: {name}
Architecture: {architecture}
Affected layer: {layer}
Severity: {severity}
Files affected:
{file_list}
Problem: {description}
{seed}
Write a concise fix suggestion using EXACTLY this format:

💡 RECOMMENDATION:
<2 sentences specific to the architecture and files listed above>

🔧 EXAMPLE FIX:
// ❌ BEFORE
<short problematic code>

// ✅ AFTER
<short corrected code>

⭐ EXTRA TIPS:
• <tip 1 specific to {architecture} architecture>
• <tip 2 specific to {architecture} architecture>"""


def generate_fix_suggestion(
    anti_pattern, files, architecture, layer, severity, description,
    use_gemini=True, detection_source="ml_model"
):
    """Generate a fix suggestion for a single anti-pattern."""
    # FIX 5: Guard against unknown patterns — log warning, use clean fallback
    if anti_pattern not in ANTI_PATTERN_CONTEXT:
        print(f"  [FixService] WARNING: unknown anti_pattern '{anti_pattern}' — using clean fallback")

    ctx = ANTI_PATTERN_CONTEXT.get(anti_pattern, ANTI_PATTERN_CONTEXT["clean"])

    result = {
        "anti_pattern"    : anti_pattern,
        "layer"           : layer or ctx.get("layer", ""),
        "severity"        : severity,
        "impact_points"   : ctx.get("impact_pts", 0),
        "problem"         : description or ctx.get("problem", ""),
        "recommendation"  : ctx.get("recommendation", ""),
        "files"           : files,
        "before_code"     : ctx.get("before_stub", ""),
        "after_code"      : ctx.get("after_stub",  ""),
        "gemini_fix"      : "",
        "ai_powered"      : False,
        "detection_source": detection_source,
    }

    if not use_gemini or anti_pattern == "clean":
        return result

    print(f"\n  → Gemini fix for '{anti_pattern}' ({architecture}) ...")
    print(f"\n  → [FixService] generate_fix_suggestion() called")
    print(f"  → [FixService] anti_pattern={anti_pattern}, use_gemini={use_gemini}, arch={architecture}")
    print(f"\n  → Gemini fix for '{anti_pattern}' ({architecture}) ...")
    gemini_text = _call_gemini(
        build_gemini_prompt(
            anti_pattern,
            files,
            architecture,
            layer or ctx.get("layer", ""),
            severity,
            description or ctx.get("problem", ""),
        )
    )
    if gemini_text:
        result["gemini_fix"] = gemini_text
        result["ai_powered"] = True
    return result


def generate_project_fixes(anti_patterns: list, architecture: str) -> list:
    """
    Generate fix suggestions for all violations in a project.

    FIX 2: Calls Gemini in PARALLEL (max 5 workers) instead of sequentially.
    Old behaviour with 8 violations: ~120 seconds.
    New behaviour with 8 violations: ~30 seconds.
    """
    # Filter out clean entries up front
    violations = [ap for ap in anti_patterns if ap.get("type", "") not in ("clean", "")]

    if not violations:
        return []

    def _fix_one(ap: dict) -> dict:
        return generate_fix_suggestion(
            anti_pattern     = ap.get("type", ""),
            files            = ap.get("files", []),
            architecture     = architecture,
            layer            = ap.get("affected_layer", ""),
            severity         = ap.get("severity", ""),
            description      = ap.get("description", ""),
            use_gemini       = True,
            detection_source = ap.get("detection_source", "ml_model"),
        )

    results    = [None] * len(violations)
    max_workers = min(5, len(violations))   # cap at 5 concurrent Gemini calls

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_idx = {
            executor.submit(_fix_one, ap): i
            for i, ap in enumerate(violations)
        }
        for future in as_completed(future_to_idx):
            idx = future_to_idx[future]
            try:
                results[idx] = future.result()
            except Exception as exc:
                print(f"  [FixService] Worker error for index {idx}: {exc}")
                # Fall back to static fix for this violation
                ap = violations[idx]
                results[idx] = generate_fix_suggestion(
                    anti_pattern     = ap.get("type", ""),
                    files            = ap.get("files", []),
                    architecture     = architecture,
                    layer            = ap.get("affected_layer", ""),
                    severity         = ap.get("severity", ""),
                    description      = ap.get("description", ""),
                    use_gemini       = False,   # static only on worker failure
                    detection_source = ap.get("detection_source", "ml_model"),
                )

    return [r for r in results if r is not None]