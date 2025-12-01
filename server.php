<?php
/**
 * Servidor API de Pôsteres
 * Arquivo único PHP para gerenciar pôsteres
 */

// Configurações
header('Access-Control-Allow-Origin: *');
header('Access-Control-Allow-Methods: GET, POST, OPTIONS');
header('Access-Control-Allow-Headers: Content-Type');
header('Content-Type: application/json');

// Tratar requisições OPTIONS (preflight)
if ($_SERVER['REQUEST_METHOD'] === 'OPTIONS') {
    http_response_code(200);
    exit();
}

// Arquivo de armazenamento
$dataFile = 'posters.json';

// Função para ler pôsteres
function getPosters($file) {
    if (!file_exists($file)) {
        return [];
    }
    
    $content = file_get_contents($file);
    $data = json_decode($content, true);
    
    return $data ? $data : [];
}

// Função para salvar pôsteres
function savePosters($file, $posters) {
    $json = json_encode($posters, JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE);
    return file_put_contents($file, $json) !== false;
}

// Função para resposta JSON
function jsonResponse($success, $data = null, $error = null) {
    $response = ['success' => $success];
    
    if ($data !== null) {
        $response = array_merge($response, $data);
    }
    
    if ($error !== null) {
        $response['error'] = $error;
    }
    
    echo json_encode($response, JSON_UNESCAPED_UNICODE);
    exit();
}

// Processar requisição
$method = $_SERVER['REQUEST_METHOD'];

if ($method === 'GET') {
    // Listar pôsteres
    $action = $_GET['action'] ?? 'list';
    
    if ($action === 'list') {
        $posters = getPosters($dataFile);
        
        // Ordenar por timestamp decrescente (mais recente primeiro)
        usort($posters, function($a, $b) {
            return $b['timestamp'] - $a['timestamp'];
        });
        
        jsonResponse(true, ['posters' => $posters]);
    } else {
        jsonResponse(false, null, 'Ação inválida');
    }
    
} elseif ($method === 'POST') {
    // Criar novo pôster
    $input = file_get_contents('php://input');
    $data = json_decode($input, true);
    
    if (!$data) {
        jsonResponse(false, null, 'Dados inválidos');
    }
    
    $action = $data['action'] ?? '';
    
    if ($action === 'create') {
        $content = $data['content'] ?? '';
        
        // Validar conteúdo
        if (empty(trim($content))) {
            jsonResponse(false, null, 'Conteúdo não pode estar vazio');
        }
        
        if (strlen($content) > 5000) {
            jsonResponse(false, null, 'Conteúdo muito longo (máximo 5000 caracteres)');
        }
        
        // Criar novo pôster
        $posters = getPosters($dataFile);
        
        $newPoster = [
            'id' => uniqid('poster_', true),
            'content' => $content,
            'timestamp' => time()
        ];
        
        $posters[] = $newPoster;
        
        // Salvar
        if (savePosters($dataFile, $posters)) {
            jsonResponse(true, ['poster' => $newPoster]);
        } else {
            jsonResponse(false, null, 'Erro ao salvar pôster');
        }
        
    } else {
        jsonResponse(false, null, 'Ação inválida');
    }
    
} else {
    jsonResponse(false, null, 'Método não permitido');
}
?>