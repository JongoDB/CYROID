# WordPress + MySQL container for Red Team Training Lab
# Contains vulnerable Acme Employee Portal plugin

FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y \
    apache2 \
    php \
    php-mysql \
    php-gd \
    php-xml \
    php-mbstring \
    php-curl \
    libapache2-mod-php \
    mysql-server \
    mysql-client \
    curl \
    wget \
    unzip \
    openssh-server \
    sudo \
    iproute2 \
    iputils-ping \
    net-tools \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Configure SSH
RUN mkdir /var/run/sshd && \
    echo 'PermitRootLogin no' >> /etc/ssh/sshd_config && \
    echo 'PasswordAuthentication yes' >> /etc/ssh/sshd_config

# Create admin user (password reused from WordPress - vulnerability)
RUN useradd -m -s /bin/bash admin && \
    echo "admin:Acme2024!" | chpasswd && \
    usermod -aG sudo admin

# Download WordPress
RUN cd /tmp && \
    wget -q https://wordpress.org/latest.tar.gz && \
    tar -xzf latest.tar.gz && \
    cp -r wordpress/* /var/www/html/ && \
    rm -rf /tmp/wordpress /tmp/latest.tar.gz && \
    rm -f /var/www/html/index.html

# Install WP-CLI (pre-installed so it works on isolated networks)
RUN curl -sO https://raw.githubusercontent.com/wp-cli/builds/gh-pages/phar/wp-cli.phar && \
    chmod +x wp-cli.phar && \
    mv wp-cli.phar /usr/local/bin/wp

# Copy vulnerable plugin
COPY acme-employee-portal /var/www/html/wp-content/plugins/acme-employee-portal

# Set permissions
RUN chown -R www-data:www-data /var/www/html && \
    chmod -R 755 /var/www/html

# Copy setup files
COPY wp-config.php /var/www/html/wp-config.php
COPY setup.sh /setup.sh
COPY mysql-init.sql /mysql-init.sql
RUN chmod +x /setup.sh

# Enable Apache modules
RUN a2enmod rewrite

EXPOSE 80 22

CMD ["/setup.sh"]
