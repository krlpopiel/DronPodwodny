/* USER CODE BEGIN Header */
/**
  ******************************************************************************
  * @file           : main.c
  * @brief          : Main program body
  ******************************************************************************
  * @attention
  *
  * Copyright (c) 2025 STMicroelectronics.
  * All rights reserved.
  *
  * This software is licensed under terms that can be found in the LICENSE file
  * in the root directory of this software component.
  * If no LICENSE file comes with this software, it is provided AS-IS.
  *
  ******************************************************************************
  */
/* USER CODE END Header */
/* Includes ------------------------------------------------------------------*/
#include "main.h"

/* Private includes ----------------------------------------------------------*/
/* USER CODE BEGIN Includes */
#include <stdio.h>
#include <string.h>
/* USER CODE END Includes */

/* Private typedef -----------------------------------------------------------*/
/* USER CODE BEGIN PTD */

/* USER CODE END PTD */

/* Private define ------------------------------------------------------------*/
/* USER CODE BEGIN PD */
#define RX_BUFFER_SIZE 256 // Rozmiar bufora DMA
/* USER CODE END PD */

/* Private macro -------------------------------------------------------------*/
/* USER CODE BEGIN PM */

/* USER CODE END PM */

/* Private variables ---------------------------------------------------------*/
UART_HandleTypeDef huart1;
UART_HandleTypeDef huart2; // Terminal (PC)
UART_HandleTypeDef huart6; // GPS
DMA_HandleTypeDef hdma_usart6_rx;

/* USER CODE BEGIN PV */

/* --- 1. Komendy u-blox (UBX) --- */
uint8_t cmd_ubx_set_nmea[] = {
    0xB5, 0x62, // Nagłówek
    0x06, 0x00, // Class: CFG, ID: PRT
    0x14, 0x00, // Długość (20 bajtów)
    0x01,       // portID: 1 (UART1)
    0x00,       // reserved0
    0x00, 0x00, // txReady: 0
    0xD0, 0x08, 0x00, 0x00, // mode: 8N1 (0x08D0)
    0x80, 0x25, 0x00, 0x00, // baudRate: 9600
    0x03, 0x00, // inProtoMask: 0x0003 (UBX + NMEA)
    0x02, 0x00, // outProtoMask: 0x0002 (tylko NMEA)
    0x00, 0x00, // flags
    0x00, 0x00, // reserved5
    0xA2, 0xB5  // Suma kontrolna
};

/* Komenda 1B: Zapisz powyższą konfigurację w pamięci stałej */
uint8_t cmd_ubx_save_config[] = {
    0xB5, 0x62, // Nagłówek
    0x06, 0x09, // Class: CFG, ID: CFG
    0x0D, 0x00, // Długość: 13
    0x00, 0x00, 0x00, 0x00, // clearMask
    0x1F, 0x11, 0x00, 0x00, // saveMask (zapisz porty i komunikaty)
    0x00, 0x00, 0x00, 0x00, // loadMask
    0x00,       // deviceMask (BBR i Flash)
    0x4F, 0x60  // Suma kontrolna
};

/* --- 2. Komendy MediaTek (MTK) --- */
const char *cmd_mtk_set_baud = "$PMTK251,9600*17\r\n";
const char *cmd_mtk_set_nmea = "$PMTK314,0,1,0,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0*28\r\n";

/* --- 3. Komendy SiRF (PSRF) --- */
const char *cmd_sirf_set_baud = "$PSRF100,1,9600,8,1,0*0E\r\n";
const char *cmd_sirf_set_gga = "$PSRF103,00,00,01,01*25\r\n";
const char *cmd_sirf_set_rmc = "$PSRF103,04,00,01,01*21\r\n";


// Bufor kołowy dla DMA
uint8_t rx_buffer[RX_BUFFER_SIZE];
// Pozycja odczytu (ogon) bufora kołowego
volatile uint16_t read_pos = 0;
/* USER CODE END PV */

/* Private function prototypes -----------------------------------------------*/
void SystemClock_Config(void);
static void MX_GPIO_Init(void);
static void MX_DMA_Init(void);
static void MX_USART1_UART_Init(void);
static void MX_USART2_UART_Init(void);
static void MX_USART6_UART_Init(void);
/* USER CODE BEGIN PFP */

//Funkcja do przesylu tablicy znakow uartem
void usart_send(USART_TypeDef *USART, const char *s){
    while(*s){
        while(!(USART->SR & USART_SR_TXE));
        USART->DR = *s++;
    }
}
//Funkcja do odbioru instrukcji uartem
uint8_t usart_getc(USART_TypeDef *USART){
	  if((USART->SR & USART_SR_RXNE) == USART_SR_RXNE){
		  return (uint8_t)(USART->DR);
	  }
	  return 0;
}


void usart_send_hex(USART_TypeDef *USART, uint8_t byte) {
    char buf[4];
    sprintf(buf, "%02X ", byte);
    usart_send(USART, buf);
}


void Set_UART6_Baudrate(uint32_t baud)
{
    // Zatrzymujemy DMA przed reinicjalizacją UART
    HAL_UART_DMAStop(&huart6);

    huart6.Init.BaudRate = baud;
    if (HAL_UART_Init(&huart6) != HAL_OK)
    {
        Error_Handler();
    }
}


/* USER CODE END PFP */

/* Private user code ---------------------------------------------------------*/
/* USER CODE BEGIN 0 */

/* USER CODE END 0 */

/**
  * @brief  The application entry point.
  * @retval int
  */
int main(void)
{

  /* USER CODE BEGIN 1 */

  /* USER CODE END 1 */

  /* MCU Configuration--------------------------------------------------------*/

  /* Reset of all peripherals, Initializes the Flash interface and the Systick. */
  HAL_Init();

  /* USER CODE BEGIN Init */

  /* USER CODE END Init */

  /* Configure the system clock */
  SystemClock_Config();

  /* USER CODE BEGIN SysInit */

  /* USER CODE END SysInit */

  /* Initialize all configured peripherals */
  MX_GPIO_Init();
  MX_DMA_Init();
  MX_USART1_UART_Init();
  MX_USART2_UART_Init();
  MX_USART6_UART_Init();
  /* USER CODE BEGIN 2 */

  // --- POCZĄTEK SEKCJI BRUTE FORCE (na UART6) ---
  // Uruchamiane przy każdym starcie, aby skonfigurować moduł GPS,
  // który traci ustawienia po wyłączeniu zasilania.

  usart_send(USART2, "Start konfiguracji GPS (Brute Force)...\r\n");

  uint32_t baudrates_to_try[] = {9600, 4800, 19200, 38400, 57600, 115200};
  uint8_t num_rates = sizeof(baudrates_to_try) / sizeof(baudrates_to_try[0]);

  for (int i = 0; i < num_rates; i++)
  {
      uint32_t current_baud = baudrates_to_try[i];

      // 1. Zmień prędkość STM32 (UART6), aby wysłać komendy
      Set_UART6_Baudrate(current_baud);

      char msg_buf[50];
      sprintf(msg_buf, "Testowanie %lu bps...\r\n", (unsigned long)current_baud);
      usart_send(USART2, msg_buf); // Używamy Twojej funkcji

      HAL_Delay(10);

      // 2. Wyślij wszystkie komendy konfiguracyjne na UART6 (używając HAL)

      // Spróbuj u-blox
      HAL_UART_Transmit(&huart6, cmd_ubx_set_nmea, sizeof(cmd_ubx_set_nmea), 100);
      HAL_Delay(50);
      HAL_UART_Transmit(&huart6, cmd_ubx_save_config, sizeof(cmd_ubx_save_config), 100);
      HAL_Delay(50);

      // Spróbuj MTK
      HAL_UART_Transmit(&huart6, (uint8_t*)cmd_mtk_set_baud, strlen(cmd_mtk_set_baud), 100);
      HAL_Delay(50);
      HAL_UART_Transmit(&huart6, (uint8_t*)cmd_mtk_set_nmea, strlen(cmd_mtk_set_nmea), 100);
      HAL_Delay(50);

      // Spróbuj SiRF
      HAL_UART_Transmit(&huart6, (uint8_t*)cmd_sirf_set_baud, strlen(cmd_sirf_set_baud), 100);
      HAL_Delay(50);
      HAL_UART_Transmit(&huart6, (uint8_t*)cmd_sirf_set_gga, strlen(cmd_sirf_set_gga), 100);
      HAL_Delay(50);
      HAL_UART_Transmit(&huart6, (uint8_t*)cmd_sirf_set_rmc, strlen(cmd_sirf_set_rmc), 100);

      HAL_Delay(200); // Czas na przetworzenie
  }

  // --- KONIEC SEKCJI BRUTE FORCE ---

  // 3. Ustaw UART6 na docelową prędkość (9600)
  Set_UART6_Baudrate(9600);

  // 4. Uruchom nasłuch DMA
  // Włączamy ciągły odbiór danych z USART6 do bufora rx_buffer
  HAL_UART_Receive_DMA(&huart6, rx_buffer, RX_BUFFER_SIZE);

  usart_send(USART2, "Koniec konfiguracji. Nasluch DMA na 9600 bps.\r\n");

  /* USER CODE END 2 */

  /* Infinite loop */
  /* USER CODE BEGIN WHILE */
  GPIOA -> ODR ^=(1<<5);
  HAL_Delay(100);
  GPIOA -> ODR ^=(1<<5);

  // Używamy Twojej funkcji
  usart_send(USART2,"READY\r\n");

  uint8_t znak;

  static char line_buffer[128];
  static uint16_t line_idx = 0;
  static uint8_t found_start = 0;

  while (1)
  {
    uint16_t write_pos = RX_BUFFER_SIZE - __HAL_DMA_GET_COUNTER(&hdma_usart6_rx);
    if (read_pos == write_pos)
		  		  {
		  			  // Używamy Twojej funkcji do wysyłania
		  			  //usart_send(USART2, "Brak nowych danych.\r\n");
		  		  }

		  		  // Przetwarzaj wszystkie nowe bajty z bufora DMA
		  		  while (read_pos != write_pos)
		  		  {
		  			  // Pobierz jeden bajt i przesuń wskaźnik odczytu
		  			  uint8_t byte = rx_buffer[read_pos];
		  			  read_pos = (read_pos + 1) % RX_BUFFER_SIZE;

		  			  // --- Logika parsera NMEA ---

		  			  if (!found_start)
		  			  {
		  				  // 1. SZUKANIE POCZĄTKU ZDANIA
		  				  if (byte == '$')
		  				  {
		  					  found_start = 1;
		  					  line_idx = 0;
		  					  line_buffer[line_idx++] = byte;
		  				  }
		  			  }
		  			  else
		  			  {
		  				  // 2. ZBIERANIE ZDANIA
		  				  if (line_idx < (sizeof(line_buffer) - 2))
		  				  {
		  					  line_buffer[line_idx++] = byte;
		  				  }

		  				  // 3. SPRAWDZANIE KOŃCA ZDANIA
		  				  if (byte == '\n')
		  				  {
		  					  line_buffer[line_idx] = '\0';
		  					  // Używamy Twojej funkcji do wysyłania
		  					  usart_send(USART2, line_buffer);

		  					  found_start = 0;
		  					  line_idx = 0;
		  				  }
		  			  }
		  		  } // koniec pętli while(read_pos != write_pos)

		  		  // Używamy Twojej funkcji do wysyłania
		  		  //usart_send(USART2, "Koniec odczytu danych GPS!\r\n");

    /* USER CODE END WHILE */

    /* USER CODE BEGIN 3 */
  }
  /* USER CODE END 3 */
}

/**
  * @brief System Clock Configuration
  * @retval None
  */
void SystemClock_Config(void)
{
  RCC_OscInitTypeDef RCC_OscInitStruct = {0};
  RCC_ClkInitTypeDef RCC_ClkInitStruct = {0};

  /** Configure the main internal regulator output voltage
  */
  __HAL_RCC_PWR_CLK_ENABLE();
  __HAL_PWR_VOLTAGESCALING_CONFIG(PWR_REGULATOR_VOLTAGE_SCALE1);

  /** Initializes the RCC Oscillators according to the specified parameters
  * in the RCC_OscInitTypeDef structure.
  */
  RCC_OscInitStruct.OscillatorType = RCC_OSCILLATORTYPE_HSI;
  RCC_OscInitStruct.HSIState = RCC_HSI_ON;
  RCC_OscInitStruct.HSICalibrationValue = RCC_HSICALIBRATION_DEFAULT;
  RCC_OscInitStruct.PLL.PLLState = RCC_PLL_NONE;
  if (HAL_RCC_OscConfig(&RCC_OscInitStruct) != HAL_OK)
  {
    Error_Handler();
  }

  /** Initializes the CPU, AHB and APB buses clocks
  */
  RCC_ClkInitStruct.ClockType = RCC_CLOCKTYPE_HCLK|RCC_CLOCKTYPE_SYSCLK
                              |RCC_CLOCKTYPE_PCLK1|RCC_CLOCKTYPE_PCLK2;
  RCC_ClkInitStruct.SYSCLKSource = RCC_SYSCLKSOURCE_HSI;
  RCC_ClkInitStruct.AHBCLKDivider = RCC_SYSCLK_DIV1;
  RCC_ClkInitStruct.APB1CLKDivider = RCC_HCLK_DIV1;
  RCC_ClkInitStruct.APB2CLKDivider = RCC_HCLK_DIV1;

  if (HAL_RCC_ClockConfig(&RCC_ClkInitStruct, FLASH_LATENCY_0) != HAL_OK)
  {
    Error_Handler();
  }
}

/**
  * @brief USART1 Initialization Function
  * @param None
  * @retval None
  */
static void MX_USART1_UART_Init(void)
{

  /* USER CODE BEGIN USART1_Init 0 */

  /* USER CODE END USART1_Init 0 */

  /* USER CODE BEGIN USART1_Init 1 */

  /* USER CODE END USART1_Init 1 */
  huart1.Instance = USART1;
  huart1.Init.BaudRate = 9600;
  huart1.Init.WordLength = UART_WORDLENGTH_8B;
  huart1.Init.StopBits = UART_STOPBITS_1;
  huart1.Init.Parity = UART_PARITY_NONE;
  huart1.Init.Mode = UART_MODE_TX_RX;
  huart1.Init.HwFlowCtl = UART_HWCONTROL_NONE;
  huart1.Init.OverSampling = UART_OVERSAMPLING_16;
  if (HAL_UART_Init(&huart1) != HAL_OK)
  {
    Error_Handler();
  }
  /* USER CODE BEGIN USART1_Init 2 */

  /* USER CODE END USART1_Init 2 */

}

/**
  * @brief USART2 Initialization Function
  * @param None
  * @retval None
  */
static void MX_USART2_UART_Init(void)
{

  /* USER CODE BEGIN USART2_Init 0 */

  /* USER CODE END USART2_Init 0 */

  /* USER CODE BEGIN USART2_Init 1 */

  /* USER CODE END USART2_Init 1 */
  huart2.Instance = USART2;
  huart2.Init.BaudRate = 9600;
  huart2.Init.WordLength = UART_WORDLENGTH_8B;
  huart2.Init.StopBits = UART_STOPBITS_1;
  huart2.Init.Parity = UART_PARITY_NONE;
  huart2.Init.Mode = UART_MODE_TX_RX;
  huart2.Init.HwFlowCtl = UART_HWCONTROL_NONE;
  huart2.Init.OverSampling = UART_OVERSAMPLING_16;
  if (HAL_UART_Init(&huart2) != HAL_OK)
  {
    Error_Handler();
  }
  /* USER CODE BEGIN USART2_Init 2 */

  /* USER CODE END USART2_Init 2 */

}

/**
  * @brief USART6 Initialization Function
  * @param None
  * @retval None
  */
static void MX_USART6_UART_Init(void)
{

  /* USER CODE BEGIN USART6_Init 0 */

  /* USER CODE END USART6_Init 0 */

  /* USER CODE BEGIN USART6_Init 1 */

  /* USER CODE END USART6_Init 1 */
  huart6.Instance = USART6;
  huart6.Init.BaudRate = 9600;
  huart6.Init.WordLength = UART_WORDLENGTH_8B;
  huart6.Init.StopBits = UART_STOPBITS_1;
  huart6.Init.Parity = UART_PARITY_NONE;
  huart6.Init.Mode = UART_MODE_TX_RX;
  huart6.Init.HwFlowCtl = UART_HWCONTROL_NONE;
  huart6.Init.OverSampling = UART_OVERSAMPLING_16;
  if (HAL_UART_Init(&huart6) != HAL_OK)
  {
    Error_Handler();
  }
  /* USER CODE BEGIN USART6_Init 2 */

  /* USER CODE END USART6_Init 2 */

}

/**
  * Enable DMA controller clock
  */
static void MX_DMA_Init(void)
{

  /* DMA controller clock enable */
  __HAL_RCC_DMA2_CLK_ENABLE();

  /* DMA interrupt init */
  /* DMA2_Stream1_IRQn interrupt configuration */
  HAL_NVIC_SetPriority(DMA2_Stream1_IRQn, 0, 0);
  HAL_NVIC_EnableIRQ(DMA2_Stream1_IRQn);

}

/**
  * @brief GPIO Initialization Function
  * @param None
  * @retval None
  */
static void MX_GPIO_Init(void)
{
  GPIO_InitTypeDef GPIO_InitStruct = {0};
  /* USER CODE BEGIN MX_GPIO_Init_1 */

  /* USER CODE END MX_GPIO_Init_1 */

  /* GPIO Ports Clock Enable */
  __HAL_RCC_GPIOA_CLK_ENABLE();
  __HAL_RCC_GPIOC_CLK_ENABLE();

  /*Configure GPIO pin Output Level */
  HAL_GPIO_WritePin(LED_GPIO_Port, LED_Pin, GPIO_PIN_RESET);

  /*Configure GPIO pin : LED_Pin */
  GPIO_InitStruct.Pin = LED_Pin;
  GPIO_InitStruct.Mode = GPIO_MODE_OUTPUT_PP;
  GPIO_InitStruct.Pull = GPIO_NOPULL;
  GPIO_InitStruct.Speed = GPIO_SPEED_FREQ_LOW;
  HAL_GPIO_Init(LED_GPIO_Port, &GPIO_InitStruct);

  /*Configure GPIO pin : STATE_Pin */
  GPIO_InitStruct.Pin = STATE_Pin;
  GPIO_InitStruct.Mode = GPIO_MODE_INPUT;
  GPIO_InitStruct.Pull = GPIO_NOPULL;
  HAL_GPIO_Init(STATE_GPIO_Port, &GPIO_InitStruct);

  /* USER CODE BEGIN MX_GPIO_Init_2 */

  /* USER CODE END MX_GPIO_Init_2 */
}

/* USER CODE BEGIN 4 */

/* USER CODE END 4 */

/**
  * @brief  This function is executed in case of error occurrence.
  * @retval None
  */
void Error_Handler(void)
{
  /* USER CODE BEGIN Error_Handler_Debug */
  /* User can add his own implementation to report the HAL error return state */
  __disable_irq();
  while (1)
  {
  }
  /* USER CODE END Error_Handler_Debug */
}
#ifdef USE_FULL_ASSERT
/**
  * @brief  Reports the name of the source file and the source line number
  * where the assert_param error has occurred.
  * @param  file: pointer to the source file name
  * @param  line: assert_param error line source number
  * @retval None
  */
void assert_failed(uint8_t *file, uint32_t line)
{
  /* USER CODE BEGIN 6 */
  /* User can add his own implementation to report the file name and line number,
     ex: printf("Wrong parameters value: file %s on line %d\r\n", file, line) */
  /* USER CODE END 6 */
}
#endif /* USE_FULL_ASSERT */
