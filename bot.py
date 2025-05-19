from telegram.ext import (
    Application, CommandHandler, MessageHandler, filters,
    ConversationHandler, ContextTypes,CallbackQueryHandler
)
from telegram import (
    Update, InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardRemove
)
from telegram.constants import ChatAction
from notion_client import Client
import google.generativeai as genai
import datetime

# Estados da conversa
NOME, URGENCIA, DESCRICAO, CONFIRMAR, MAIS_TAREFAS = range(5)

# Configurações APIs
genai.configure(api_key="SUA API GEMINI")
model = genai.GenerativeModel("gemini-1.5-flash")
notion = Client(auth="API NOTION")
notion_database_id = "SEU ID DO BANCO DO NOTION"

# Teclado para urgência
urgencia_inline_keyboard = InlineKeyboardMarkup([
    [InlineKeyboardButton("Prioridade", callback_data="Prioridade"),
     InlineKeyboardButton("Importante", callback_data="Importante")],
    [InlineKeyboardButton("Urgente", callback_data="Urgente"),
     InlineKeyboardButton("Não urgente", callback_data="Não urgente")],
    [InlineKeyboardButton("Não importante", callback_data="Não importante")]
])

sim_nao_inline_keyboard = InlineKeyboardMarkup([
    [InlineKeyboardButton("Sim", callback_data="sim"),
     InlineKeyboardButton("Não", callback_data="nao")]
])

async def start_rotina(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Oi! Vou te ajudar a organizar suas tarefas no Notion.\n"
        "Para começar, me diga o nome da tarefa.",
        reply_markup=ReplyKeyboardRemove()
    )
    return NOME

async def receber_nome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    nome = update.message.text.strip()
    if not nome:
        await update.message.reply_text("Por favor, envie um nome válido para a tarefa.")
        return NOME
    context.user_data["nome_tarefa"] = nome
    await update.message.reply_text("Qual a urgência da tarefa?", reply_markup=urgencia_inline_keyboard)
    return URGENCIA

async def receber_urgencia_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    urgencia = query.data
    context.user_data["urgencia"] = urgencia
    await query.message.reply_text("Agora descreva a tarefa com detalhes.", reply_markup=ReplyKeyboardRemove())
    return DESCRICAO

async def receber_descricao(update: Update, context: ContextTypes.DEFAULT_TYPE):
    descricao = update.message.text.strip()
    if not descricao:
        await update.message.reply_text("Por favor, envie uma descrição válida.")
        return DESCRICAO
    context.user_data["descricao"] = descricao

    nome = context.user_data["nome_tarefa"]
    urgencia = context.user_data["urgencia"]

    resumo = (
        f"Confira os dados da tarefa:\n\n"
        f"Nome: {nome}\n"
        f"Urgência: {urgencia}\n"
        f"Descrição: {descricao}\n\n"
        "Confirma o cadastro dessa tarefa?"
    )
    await update.message.reply_text(resumo, reply_markup=sim_nao_inline_keyboard)
    return CONFIRMAR

async def confirmar_tarefa_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    resposta = query.data.lower()

    if resposta == "sim":
        nome = context.user_data["nome_tarefa"]
        urgencia = context.user_data["urgencia"]
        descricao = context.user_data["descricao"]
        data = datetime.date.today().isoformat()

        def dividir_texto(texto, limite=2000):
            return [texto[i:i + limite] for i in range(0, len(texto), limite)]

        blocos = dividir_texto(descricao)
        children_blocks = [
            {
                "object": "block",
                "type": "heading_2",
                "heading_2": {
                    "rich_text": [{"type": "text", "text": {"content": bloco}}]
                }
            }
            for bloco in blocos
        ]

        try:
            notion.pages.create(
                parent={"database_id": notion_database_id},
                properties={
                    "Item": {"title": [{"text": {"content": nome}}]},
                    "Urgência": {"multi_select": [{"name": urgencia}]},
                    "Data": {"date": {"start": data}}}
                ,
                children=children_blocks
            )
        except Exception as e:
            await query.message.reply_text("Erro ao salvar no Notion. Tente novamente mais tarde.")
            print(f"Erro Notion: {e}")
            return ConversationHandler.END

        await query.message.reply_text(
            f"Tarefa '{nome}' criada!\n🗓 Data: {data}\n⚠️ Urgência: {urgencia}",
            reply_markup=ReplyKeyboardRemove()
        )
        await query.message.reply_text("Quer adicionar mais alguma tarefa?", reply_markup=sim_nao_inline_keyboard)
        return MAIS_TAREFAS

    else:
        await query.message.reply_text("Ok, vamos começar de novo. Qual o nome da tarefa?")
        return NOME

async def mais_tarefas_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    resposta = query.data.lower()

    if resposta == "sim":
        await query.message.reply_text("Qual o nome da próxima tarefa?")
        return NOME
    else:
        await query.message.reply_text("Beleza! Se precisar, é só chamar.")
        return ConversationHandler.END

async def cancelar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Cancelado. Se precisar, só chamar.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

async def ajuda(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Como usar o bot:\n"
        "- Envie 'rotina' para começar a adicionar uma tarefa.\n"
        "- Você será guiado com perguntas e botões para facilitar.\n"
        "- Pode cancelar a qualquer momento com /cancelar.\n"
        "Qualquer dúvida, só chamar!"
    )

def main():
    app = Application.builder().token("CODE TELEGRAM").build()

    conv_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^rotina$"), start_rotina)],
        states={
            NOME: [MessageHandler(filters.TEXT & ~filters.COMMAND, receber_nome)],
            URGENCIA: [MessageHandler(filters.TEXT & ~filters.COMMAND, receber_nome),  # fallback
                       CallbackQueryHandler(receber_urgencia_callback)],
            DESCRICAO: [MessageHandler(filters.TEXT & ~filters.COMMAND, receber_descricao)],
            CONFIRMAR: [CallbackQueryHandler(confirmar_tarefa_callback)],
            MAIS_TAREFAS: [CallbackQueryHandler(mais_tarefas_callback)],
        },
        fallbacks=[CommandHandler("cancelar", cancelar)],
    )

    app.add_handler(conv_handler)
    app.add_handler(CommandHandler("help", ajuda))

    print("Bot iniciado...")
    app.run_polling()

if __name__ == "__main__":
    main()
