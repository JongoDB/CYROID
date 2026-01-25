<?php
/**
 * Plugin Name: Acme Employee Portal
 * Description: Internal employee directory and resources
 * Version: 1.0.0
 * Author: Acme Widgets IT
 */

if (!defined('ABSPATH')) exit;

register_activation_hook(__FILE__, 'acme_portal_activate');

function acme_portal_activate() {
    global $wpdb;
    $table = $wpdb->prefix . 'acme_employees';

    $sql = "CREATE TABLE IF NOT EXISTS $table (
        id INT AUTO_INCREMENT PRIMARY KEY,
        employee_id VARCHAR(20) NOT NULL,
        full_name VARCHAR(100) NOT NULL,
        department VARCHAR(50),
        email VARCHAR(100),
        phone VARCHAR(20),
        notes TEXT,
        vpn_username VARCHAR(50),
        vpn_password VARCHAR(100),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )";

    require_once(ABSPATH . 'wp-admin/includes/upgrade.php');
    dbDelta($sql);

    // Seed with employee data including VPN creds
    $wpdb->insert($table, array(
        'employee_id' => 'EMP001',
        'full_name' => 'John Smith',
        'department' => 'IT Support',
        'email' => 'jsmith@acmewidgets.local',
        'phone' => '555-0101',
        'notes' => 'IT admin, has server access',
        'vpn_username' => 'jsmith',
        'vpn_password' => 'Summer2024'
    ));

    $wpdb->insert($table, array(
        'employee_id' => 'EMP002',
        'full_name' => 'Mary Williams',
        'department' => 'Accounting',
        'email' => 'mwilliams@acmewidgets.local',
        'phone' => '555-0102',
        'notes' => 'Handles payroll',
        'vpn_username' => 'mwilliams',
        'vpn_password' => 'Welcome123'
    ));

    $wpdb->insert($table, array(
        'employee_id' => 'EMP003',
        'full_name' => 'Backup Service',
        'department' => 'IT',
        'email' => 'svc_backup@acmewidgets.local',
        'phone' => '',
        'notes' => 'Service account for backups - DO NOT DELETE',
        'vpn_username' => 'svc_backup',
        'vpn_password' => 'Backup2024'
    ));
}

add_shortcode('employee_directory', 'acme_employee_directory');

function acme_employee_directory($atts) {
    global $wpdb;
    $table = $wpdb->prefix . 'acme_employees';

    $output = '<div class="acme-employee-directory">';
    $output .= '<h2>Employee Directory</h2>';
    $output .= '<form method="GET" action="">';
    $output .= '<input type="text" name="search" placeholder="Search employees..." value="' . esc_attr($_GET['search'] ?? '') . '">';
    $output .= '<button type="submit">Search</button>';
    $output .= '</form>';

    // VULNERABLE: SQL Injection via search parameter
    $search = $_GET['search'] ?? '';

    if (!empty($search)) {
        // INTENTIONALLY VULNERABLE - DO NOT FIX
        $query = "SELECT id, employee_id, full_name, department, email, phone FROM $table WHERE full_name LIKE '%$search%' OR department LIKE '%$search%' OR employee_id LIKE '%$search%'";
    } else {
        $query = "SELECT id, employee_id, full_name, department, email, phone FROM $table";
    }

    $employees = $wpdb->get_results($query);

    if ($employees) {
        $output .= '<table class="employee-table">';
        $output .= '<tr><th>ID</th><th>Name</th><th>Department</th><th>Email</th><th>Phone</th></tr>';

        foreach ($employees as $emp) {
            $output .= '<tr>';
            $output .= '<td>' . esc_html($emp->employee_id) . '</td>';
            $output .= '<td><a href="?employee_id=' . $emp->id . '">' . esc_html($emp->full_name) . '</a></td>';
            $output .= '<td>' . esc_html($emp->department) . '</td>';
            $output .= '<td>' . esc_html($emp->email) . '</td>';
            $output .= '<td>' . esc_html($emp->phone) . '</td>';
            $output .= '</tr>';
        }
        $output .= '</table>';
    } else {
        $output .= '<p>No employees found.</p>';
    }

    // Employee detail view - ALSO VULNERABLE
    if (isset($_GET['employee_id'])) {
        $emp_id = $_GET['employee_id'];
        $detail_query = "SELECT * FROM $table WHERE id = $emp_id";
        $employee = $wpdb->get_row($detail_query);

        if ($employee) {
            $output .= '<div class="employee-detail">';
            $output .= '<h3>Employee Details</h3>';
            $output .= '<p><strong>Name:</strong> ' . esc_html($employee->full_name) . '</p>';
            $output .= '<p><strong>Department:</strong> ' . esc_html($employee->department) . '</p>';
            $output .= '<p><strong>Email:</strong> ' . esc_html($employee->email) . '</p>';
            // VULNERABLE: XSS - notes field not escaped
            $output .= '<p><strong>Notes:</strong> ' . $employee->notes . '</p>';
            $output .= '</div>';
        }
    }

    $output .= '</div>';
    return $output;
}

add_action('admin_menu', 'acme_portal_admin_menu');

function acme_portal_admin_menu() {
    add_menu_page(
        'Employee Portal',
        'Employees',
        'manage_options',
        'acme-employees',
        'acme_portal_admin_page',
        'dashicons-groups'
    );
}

function acme_portal_admin_page() {
    global $wpdb;
    $table = $wpdb->prefix . 'acme_employees';

    if (($_POST['action'] ?? '') === 'add_employee') {
        $wpdb->insert($table, array(
            'employee_id' => sanitize_text_field($_POST['employee_id']),
            'full_name' => sanitize_text_field($_POST['full_name']),
            'department' => sanitize_text_field($_POST['department']),
            'email' => sanitize_email($_POST['email']),
            'phone' => sanitize_text_field($_POST['phone']),
            'notes' => $_POST['notes'], // VULNERABLE: No sanitization for XSS
            'vpn_username' => sanitize_text_field($_POST['vpn_username']),
            'vpn_password' => $_POST['vpn_password']
        ));
        echo '<div class="notice notice-success"><p>Employee added!</p></div>';
    }

    $employees = $wpdb->get_results("SELECT * FROM $table");

    ?>
    <div class="wrap">
        <h1>Acme Employee Portal</h1>
        <h2>Add Employee</h2>
        <form method="POST">
            <input type="hidden" name="action" value="add_employee">
            <table class="form-table">
                <tr><td>Employee ID:</td><td><input type="text" name="employee_id" required></td></tr>
                <tr><td>Full Name:</td><td><input type="text" name="full_name" required></td></tr>
                <tr><td>Department:</td><td><input type="text" name="department"></td></tr>
                <tr><td>Email:</td><td><input type="email" name="email"></td></tr>
                <tr><td>Phone:</td><td><input type="text" name="phone"></td></tr>
                <tr><td>Notes:</td><td><textarea name="notes"></textarea></td></tr>
                <tr><td>VPN Username:</td><td><input type="text" name="vpn_username"></td></tr>
                <tr><td>VPN Password:</td><td><input type="text" name="vpn_password"></td></tr>
            </table>
            <button type="submit" class="button button-primary">Add Employee</button>
        </form>
        <h2>Current Employees</h2>
        <table class="wp-list-table widefat fixed striped">
            <thead><tr><th>ID</th><th>Name</th><th>Department</th><th>Email</th><th>VPN User</th></tr></thead>
            <tbody>
                <?php foreach ($employees as $emp): ?>
                <tr>
                    <td><?php echo esc_html($emp->employee_id); ?></td>
                    <td><?php echo esc_html($emp->full_name); ?></td>
                    <td><?php echo esc_html($emp->department); ?></td>
                    <td><?php echo esc_html($emp->email); ?></td>
                    <td><?php echo esc_html($emp->vpn_username); ?></td>
                </tr>
                <?php endforeach; ?>
            </tbody>
        </table>
    </div>
    <?php
}

add_action('wp_head', 'acme_portal_styles');

function acme_portal_styles() {
    ?>
    <style>
        .acme-employee-directory { max-width: 900px; margin: 20px auto; }
        .acme-employee-directory form { margin-bottom: 20px; }
        .acme-employee-directory input[type="text"] { padding: 8px; width: 300px; }
        .acme-employee-directory button { padding: 8px 16px; }
        .employee-table { width: 100%; border-collapse: collapse; }
        .employee-table th, .employee-table td { border: 1px solid #ddd; padding: 10px; text-align: left; }
        .employee-table th { background: #f5f5f5; }
        .employee-table tr:hover { background: #f9f9f9; }
        .employee-detail { margin-top: 20px; padding: 20px; background: #f5f5f5; border-radius: 5px; }
    </style>
    <?php
}
