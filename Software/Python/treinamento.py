# Versões das bibliotecas utilizadas:
# pandas: 2.3.0
# scikit-learn: 1.7.0
# matplotlib: 3.10.3
# seaborn: 0.13.2
# joblib: 1.5.1
# scipy: 1.16.0

import pandas as pd
from sklearn.model_selection import train_test_split, RandomizedSearchCV
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix
from sklearn.preprocessing import MinMaxScaler
import matplotlib.pyplot as plt
import seaborn as sns
import joblib
from scipy.stats import randint

# 1. Carrega o dataset
dataset = pd.read_csv("dataset_nariz_eletronico.csv")

# 2. Separa as colunas de entrada (X) e saída (y)
X = dataset[["MQ3", "MQ5", "MQ6", "MQ8"]]
y = dataset["Tipo_álcool"]

# 3. Divide os dados em treino (80%) e teste (20%)
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

# Normalização dos dados
scaler = MinMaxScaler()
X_train_scaled = scaler.fit_transform(X_train.values)
X_test_scaled = scaler.transform(X_test.values)

# --- Configuração para o Randomized Search ---
# Define o modelo base
rf = RandomForestClassifier(random_state=42)

param_distributions = {
    'n_estimators': randint(low=50, high=500),
    'max_features': ['sqrt', 'log2', None],
    'max_depth': randint(low=5, high=50),
    'min_samples_split': randint(low=2, high=20),
    'min_samples_leaf': randint(low=1, high=10),
    'bootstrap': [True, False]
}

random_search = RandomizedSearchCV(estimator=rf,
                                   param_distributions=param_distributions,
                                   n_iter=100,
                                   cv=5,
                                   scoring='accuracy',
                                   random_state=42,
                                   n_jobs=-1,
                                   verbose=2)

# 4. Treina o modelo COM Randomized Search
random_search.fit(X_train_scaled, y_train)

model = random_search.best_estimator_

print("\n===== MELHORES HIPERPARÂMETROS ENCONTRADOS =====")
print(random_search.best_params_)
print(f"Melhor pontuação (acurácia) com validação cruzada: {random_search.best_score_:.2f}")

# 5. Faz previsões com os dados de teste (já escalados) usando o melhor modelo
y_pred = model.predict(X_test_scaled)

# 6. Avaliação do modelo final
print("\n===== AVALIAÇÃO DO MODELO FINAL (no conjunto de teste) =====")
print(f"Acurácia: {accuracy_score(y_test, y_pred):.2f}")
print("\nRelatório de Classificação:")
print(classification_report(y_test, y_pred))

# 7. Salva o modelo treinado E o scaler
joblib.dump(model, "modelo_nariz_eletronico.pkl")
joblib.dump(scaler, "scaler_nariz_eletronico.pkl")
print("Modelo salvo como modelo_nariz_eletronico.pkl")
print("Scaler salvo como scaler_nariz_eletronico.pkl")

# 8. Matriz de Confusão
cm = confusion_matrix(y_test, y_pred, labels=model.classes_)

plt.figure(figsize=(6,5))
sns.heatmap(cm, annot=True, fmt='d', cmap='Blues',
            xticklabels=model.classes_, yticklabels=model.classes_)
plt.xlabel("Classe Predita")
plt.ylabel("Classe Verdadeira")
plt.title("Matriz de Confusão")
plt.tight_layout()
plt.show()
