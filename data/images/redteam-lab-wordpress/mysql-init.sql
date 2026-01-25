-- MySQL initialization for Red Team Training Lab

CREATE DATABASE IF NOT EXISTS wordpress;
CREATE USER IF NOT EXISTS 'wp_user'@'localhost' IDENTIFIED BY 'Acme2024!';
GRANT ALL PRIVILEGES ON wordpress.* TO 'wp_user'@'localhost';

-- Secrets database (SQLi can discover this)
CREATE DATABASE IF NOT EXISTS secrets;

CREATE TABLE IF NOT EXISTS secrets.admin_accounts (
    id INT AUTO_INCREMENT PRIMARY KEY,
    service VARCHAR(50),
    username VARCHAR(50),
    password VARCHAR(100),
    notes TEXT
);

INSERT INTO secrets.admin_accounts (service, username, password, notes) VALUES
('RouterOS', 'admin', 'Mikr0t1k!', 'Main router admin'),
('RouterOS', 'backup', 'backup123', 'Backup account'),
('Domain Admin', 'Administrator', 'Adm1n2024', 'AD domain admin'),
('Backup Service', 'svc_backup', 'Backup2024', 'Has DCSync rights');

-- Misconfiguration: wp_user can read secrets
GRANT SELECT ON secrets.* TO 'wp_user'@'localhost';

FLUSH PRIVILEGES;
