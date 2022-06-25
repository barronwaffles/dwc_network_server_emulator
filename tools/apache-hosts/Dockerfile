FROM httpd:2.4-alpine

ENV APACHE_LOG_DIR=/usr/local/apache2/logs

# Change this if you have your own domain name set up
# Otherwise, you will need to set up a DNS server to point nintendowifi.net to your IP address
ENV HOST=nintendowifi.net

# TODO: do in one line
RUN echo $'IncludeOptional /usr/local/apache2/vhost.d/*.conf\n\
ServerName localhost\n\
HttpProtocolOptions Unsafe' >> conf/httpd.conf
RUN sed -i 's/^#LoadModule proxy_module/LoadModule proxy_module/' conf/httpd.conf
RUN sed -i 's/^#LoadModule proxy_http_module/LoadModule proxy_http_module/' conf/httpd.conf

COPY *.conf vhost.d/
