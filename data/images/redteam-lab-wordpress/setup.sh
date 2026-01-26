#!/bin/bash
set -e

# Configure network routing (VyOS router is gateway at .1)
# This is needed because CYROID uses VyOS as gateway instead of Docker bridge
configure_routing() {
    local ip=$(hostname -I | awk '{print $1}')
    if [ -n "$ip" ]; then
        # Extract network prefix and set gateway to .1
        local gateway=$(echo "$ip" | sed 's/\.[0-9]*$/.1/')

        # Check if we already have a default route
        if ! ip route show default | grep -q "via $gateway"; then
            # Delete existing default route if any
            ip route del default 2>/dev/null || true
            # Add route via VyOS router
            ip route add default via "$gateway" 2>/dev/null || true
            echo "Configured default route via $gateway"
        fi
    fi
}
configure_routing

# Start MySQL
service mysql start

# Wait for MySQL
until mysqladmin ping -h localhost --silent; do
    sleep 1
done

# Fix MySQL socket permissions for Apache/PHP access
# The mysqld directory is created with 700 permissions by default,
# which prevents www-data from accessing the socket
chmod 755 /var/run/mysqld/

# Initialize database
mysql < /mysql-init.sql

# Start SSH
service ssh start

# Install WordPress if not done (WP-CLI is pre-installed in the image)
if ! wp core is-installed --path=/var/www/html --allow-root 2>/dev/null; then
    wp core install \
        --path=/var/www/html \
        --url="http://$(hostname -I | awk '{print $1}')" \
        --title="Acme Widgets Inc." \
        --admin_user="admin" \
        --admin_password="Acme2024!" \
        --admin_email="admin@acmewidgets.local" \
        --allow-root

    # Create users
    wp user create jsmith jsmith@acmewidgets.local \
        --role=editor --user_pass="Summer2024" \
        --path=/var/www/html --allow-root

    wp user create mwilliams mwilliams@acmewidgets.local \
        --role=author --user_pass="Welcome123" \
        --path=/var/www/html --allow-root

    # Activate plugin
    wp plugin activate acme-employee-portal --path=/var/www/html --allow-root

    # Create employee directory page
    # Using slug 'employees' so gobuster finds it with common wordlists
    wp post create \
        --post_type=page \
        --post_title='Employee Directory' \
        --post_name='employees' \
        --post_content='[employee_directory]' \
        --post_status=publish \
        --path=/var/www/html \
        --allow-root

    # Configure permalinks for pretty URLs
    wp rewrite structure '/%postname%/' --path=/var/www/html --allow-root
    wp rewrite flush --path=/var/www/html --allow-root

    # Manually create .htaccess (wp rewrite flush doesn't always create it)
    if [ ! -f /var/www/html/.htaccess ]; then
        cat > /var/www/html/.htaccess << 'HTACCESS'
# BEGIN WordPress
<IfModule mod_rewrite.c>
RewriteEngine On
RewriteBase /
RewriteRule ^index\.php$ - [L]
RewriteCond %{REQUEST_FILENAME} !-f
RewriteCond %{REQUEST_FILENAME} !-d
RewriteRule . /index.php [L]
</IfModule>
# END WordPress
HTACCESS
        chown www-data:www-data /var/www/html/.htaccess
        chmod 644 /var/www/html/.htaccess
        echo "Created .htaccess for permalinks"
    fi

    echo "WordPress installation complete!"
fi

# Configure Apache to allow .htaccess overrides for permalinks
if ! grep -q "AllowOverride All" /etc/apache2/apache2.conf; then
    sed -i '/<Directory \/var\/www\/>/,/<\/Directory>/ s/AllowOverride None/AllowOverride All/' /etc/apache2/apache2.conf
    echo "Enabled AllowOverride All for /var/www/"
fi

# Start Apache in foreground
exec apache2ctl -D FOREGROUND
