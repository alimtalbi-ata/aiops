<?php
// CI-only disposable GLPI database fixture. Never run against a deployed instance.
if (PHP_SAPI !== 'cli' || getenv('AIOPS_GLPI_DISPOSABLE') !== 'v3-glpi-ci'
    || getenv('GLPI_DB_HOST') !== 'db' || getenv('GLPI_DB_NAME') !== 'glpi'
    || getenv('GLPI_DB_USER') !== 'glpi') {
    throw new RuntimeException('Disposable CI database required');
}
$app = getenv('AIOPS_GLPI_APP_TOKEN');
$user = getenv('AIOPS_GLPI_USER_TOKEN');
foreach ([$app, $user] as $token) {
    if (!is_string($token) || !preg_match('/^[a-f0-9]{48}$/D', $token)) {
        throw new RuntimeException('Invalid fixture token');
    }
}
require_once '/var/www/glpi/vendor/autoload.php';
$kernel = new \Glpi\Kernel\Kernel();
$kernel->boot();
if (!defined('GLPI_VERSION') || GLPI_VERSION !== '12.0.2') {
    throw new RuntimeException('Unexpected GLPI version');
}
mysqli_report(MYSQLI_REPORT_ERROR | MYSQLI_REPORT_STRICT);
$db = new mysqli('db', 'glpi', getenv('GLPI_DB_PASSWORD'), 'glpi', 3306);
$db->set_charset('utf8mb4');
$key = new GLPIKey();
// Fixture uses the default administrator of this freshly installed lab only.
// No production authorization or least-privilege certification is implied.
$row = $db->query("SELECT id FROM glpi_users WHERE name='glpi' AND is_active=1")->fetch_assoc();
if (!$row || (int)$row['id'] <= 0) {
    throw new RuntimeException('Default fixture user not installed');
}
$uid = (int)$row['id'];
Config::setConfigurationValues('core', [
    'enable_api' => '1',
    'enable_api_login_external_token' => '1',
    'enable_api_login_credentials' => '0',
]);
$encryptedUser = $key->encrypt($user);
$encryptedApp = $key->encrypt($app);
$db->begin_transaction();
try {
    $stmt = $db->prepare('UPDATE glpi_users SET api_token=?, api_token_date=NOW() WHERE id=?');
    $stmt->bind_param('si', $encryptedUser, $uid);
    $stmt->execute();
    if ($stmt->affected_rows !== 1) {
        throw new RuntimeException('Fixture user update failed');
    }
    // Disable any default anonymous API client in this disposable database.
    $db->query('UPDATE glpi_apiclients SET is_active=0');
    $stmt = $db->prepare("INSERT INTO glpi_apiclients (name,is_active,app_token,app_token_date) VALUES ('AIOPS-V3-CI',1,?,NOW())");
    $stmt->bind_param('s', $encryptedApp);
    $stmt->execute();
    $db->query("INSERT INTO glpi_tickets (name,content,entities_id,status,date,date_creation,date_mod) VALUES ('AIOPS-V3-CI-TICKET','Synthetic latency regression',0,1,NOW(),NOW(),NOW())");
    $tid = $db->insert_id;
    $stmt = $db->prepare("INSERT INTO glpi_itilfollowups (itemtype,items_id,users_id,content,is_private,date,date_creation,date_mod) VALUES ('Ticket',?,?,'AIOPS-V3-CI-FOLLOWUP',1,NOW(),NOW(),NOW())");
    $stmt->bind_param('ii', $tid, $uid);
    $stmt->execute();
    $fid = $db->insert_id;
    if ($tid <= 0 || $fid <= 0) {
        throw new RuntimeException('Fixture insert failed');
    }
    $db->commit();
} catch (Throwable $e) {
    $db->rollback();
    throw $e;
}
echo json_encode(['ticket_id' => $tid, 'followup_id' => $fid], JSON_THROW_ON_ERROR), PHP_EOL;
