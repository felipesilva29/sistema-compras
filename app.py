import os
from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
import datetime

# --- CONFIGURAÇÃO INICIAL ---
app = Flask(__name__)
CORS(app)

basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'compras.db') # Novo nome de arquivo de BD
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# --- MODELOS DO BANCO DE DADOS ---

class Evento(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(150), unique=True, nullable=False)

    def to_dict(self):
        return {'id': self.id, 'nome': self.nome}

class Pedido(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    solicitante = db.Column(db.String(100), nullable=False)
    descricao = db.Column(db.Text, nullable=False)
    valor_estimado = db.Column(db.Float, nullable=False)
    prazo_compra = db.Column(db.Date, nullable=False)
    data_aprovada = db.Column(db.Date, nullable=True)
    data_utilizacao = db.Column(db.Date, nullable=False)
    evento_nome = db.Column(db.String(150), default="Sem vínculo a evento")
    status = db.Column(db.String(50), default='Pendente', nullable=False)
    forma_pagamento = db.Column(db.String(50), nullable=True)
    observacoes = db.Column(db.Text, nullable=True)
    historico = db.Column(db.JSON, default=[])
    data_criacao = db.Column(db.DateTime, default=datetime.datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'requesterName': self.solicitante,
            'description': self.descricao,
            'estimatedValue': self.valor_estimado,
            'deadlineDate': self.prazo_compra.isoformat() if self.prazo_compra else None,
            'authorizedDate': self.data_aprovada.isoformat() if self.data_aprovada else None,
            'useDate': self.data_utilizacao.isoformat() if self.data_utilizacao else None,
            'eventName': self.evento_nome,
            'status': self.status,
            'paymentMethod': self.forma_pagamento,
            'additionalNotes': self.observacoes,
            'history': self.historico,
            'createdAt': self.data_criacao.isoformat()
        }

# --- API (ROTAS) ---

# Rotas para Eventos
@app.route('/api/eventos', methods=['GET', 'POST'])
def gerenciar_eventos():
    if request.method == 'GET':
        eventos = Evento.query.all()
        return jsonify([evento.to_dict() for evento in eventos])
    if request.method == 'POST':
        dados = request.json
        if not dados or not dados.get('nome'):
            return jsonify({'error': 'Nome do evento é obrigatório'}), 400
        novo_evento = Evento(nome=dados['nome'])
        db.session.add(novo_evento)
        db.session.commit()
        return jsonify(novo_evento.to_dict()), 201

@app.route('/api/eventos/<int:id>', methods=['DELETE'])
def deletar_evento(id):
    evento = Evento.query.get_or_404(id)
    # Atualiza pedidos vinculados antes de deletar
    pedidos_afetados = Pedido.query.filter_by(evento_nome=evento.nome).all()
    for pedido in pedidos_afetados:
        pedido.evento_nome = "Sem vínculo a evento"
    db.session.delete(evento)
    db.session.commit()
    return jsonify({'message': 'Evento deletado com sucesso'}), 200

# Rotas para Pedidos
@app.route('/api/pedidos', methods=['GET', 'POST'])
def gerenciar_pedidos():
    if request.method == 'GET':
        pedidos = Pedido.query.order_by(Pedido.id.desc()).all()
        return jsonify([pedido.to_dict() for pedido in pedidos])
    if request.method == 'POST':
        dados = request.json
        novo_pedido = Pedido(
            solicitante=dados['requesterName'],
            descricao=dados['description'],
            valor_estimado=dados['estimatedValue'],
            prazo_compra=datetime.datetime.strptime(dados['deadlineDate'], '%Y-%m-%d').date(),
            data_utilizacao=datetime.datetime.strptime(dados['useDate'], '%Y-%m-%d').date(),
            evento_nome=dados.get('eventName', "Sem vínculo a evento"),
            status='Pendente'
        )
        novo_pedido.historico = [{
            'action': 'Criação', 
            'date': datetime.datetime.utcnow().isoformat(), 
            'details': 'Pedido criado'
        }]
        db.session.add(novo_pedido)
        db.session.commit()
        return jsonify(novo_pedido.to_dict()), 201

@app.route('/api/pedidos/<int:id>', methods=['GET', 'PUT', 'DELETE'])
def gerenciar_pedido_unico(id):
    pedido = Pedido.query.get_or_404(id)
    if request.method == 'GET':
        return jsonify(pedido.to_dict())
    if request.method == 'DELETE':
        db.session.delete(pedido)
        db.session.commit()
        return jsonify({'message': 'Pedido deletado'}), 200
    if request.method == 'PUT':
        dados = request.json
        historico_atual = list(pedido.historico) # Copia o histórico
        
        # Atualiza os campos do pedido
        if 'requesterName' in dados: pedido.solicitante = dados['requesterName']
        if 'description' in dados: pedido.descricao = dados['description']
        if 'estimatedValue' in dados: pedido.valor_estimado = dados['estimatedValue']
        if 'deadlineDate' in dados: pedido.prazo_compra = datetime.datetime.strptime(dados['deadlineDate'], '%Y-%m-%d').date()
        if 'useDate' in dados: pedido.data_utilizacao = datetime.datetime.strptime(dados['useDate'], '%Y-%m-%d').date()
        if 'eventName' in dados: pedido.evento_nome = dados['eventName']
        if 'additionalNotes' in dados: pedido.observacoes = dados['additionalNotes']
        
        # Lógica para mudança de status e histórico
        status_antigo = pedido.status
        if 'status' in dados and dados['status'] != status_antigo:
            pedido.status = dados['status']
            historico_atual.append({
                'action': 'Alteração de Status', 
                'date': datetime.datetime.utcnow().isoformat(), 
                'details': f'Status alterado de "{status_antigo}" para "{pedido.status}"'
            })
            if pedido.status == 'Aprovado':
                pedido.data_aprovada = datetime.datetime.strptime(dados['authorizedDate'], '%Y-%m-%d').date()
                pedido.forma_pagamento = dados['paymentMethod']
        
        pedido.historico = historico_atual
        db.session.commit()
        return jsonify(pedido.to_dict())

# --- INICIALIZAÇÃO ---
with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)