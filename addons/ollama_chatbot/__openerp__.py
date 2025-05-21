# -*- coding: utf-8 -*-
{
    'name': 'Ollama Chatbot Integration',
    'version': '1.0',
    'author': 'AI Agent',
    'category': 'Tools',
    'description': '''
Integrates Ollama chatbot to answer questions about sales, attendances, and bank statements.
    ''',
    'website': '',
    'depends': ['base', 'sale', 'hr_attendance', 'account', 'web'],
    'data': [
        'data/ollama_chatbot_config_data.xml',
        'security/ir.model.access.csv',
        'views/ollama_chatbot_views.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': True,
}
