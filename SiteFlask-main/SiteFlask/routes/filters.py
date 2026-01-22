def register_filters(app):
    @app.template_filter('number_format')
    def number_format(value):
        try:
            return f"{int(value):,}".replace(",", " ")
        except:
            return value
    
    @app.template_filter('format_date')
    def format_date(value):
        from datetime import datetime
        if isinstance(value, datetime):
            return value.strftime('%d.%m.%Y %H:%M')
        return value