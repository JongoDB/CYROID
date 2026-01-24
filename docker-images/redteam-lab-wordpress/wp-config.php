<?php
define('DB_NAME', 'wordpress');
define('DB_USER', 'wp_user');
define('DB_PASSWORD', 'Acme2024!');
define('DB_HOST', 'localhost');
define('DB_CHARSET', 'utf8');
define('DB_COLLATE', '');

define('AUTH_KEY',         'redteam-lab-auth-key');
define('SECURE_AUTH_KEY',  'redteam-lab-secure-auth-key');
define('LOGGED_IN_KEY',    'redteam-lab-logged-in-key');
define('NONCE_KEY',        'redteam-lab-nonce-key');
define('AUTH_SALT',        'redteam-lab-auth-salt');
define('SECURE_AUTH_SALT', 'redteam-lab-secure-auth-salt');
define('LOGGED_IN_SALT',   'redteam-lab-logged-in-salt');
define('NONCE_SALT',       'redteam-lab-nonce-salt');

$table_prefix = 'wp_';
define('WP_DEBUG', false);

if (!defined('ABSPATH')) {
    define('ABSPATH', __DIR__ . '/');
}

require_once ABSPATH . 'wp-settings.php';
