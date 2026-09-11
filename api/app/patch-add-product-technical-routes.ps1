$path = "C:\ai-platform\api\app\openapi-gpt.json"
$backup = "C:\ai-platform\api\app\openapi-gpt.backup-before-product-technical.json"

Copy-Item $path $backup -Force

$json = Get-Content $path -Raw | ConvertFrom-Json

# ------------------------------------------------------------
# Route 1: /products/search
# ------------------------------------------------------------
$productSearchRoute = "/products/search"

$productSearchObject = [ordered]@{
  get = [ordered]@{
    tags = @("products")
    summary = "Search Product Context"
    description = "Zoekt in vw_gpt_product_search. Familie-bewust zoeken voor GPT-productvragen."
    operationId = "search_product_context_products_search_get"
    parameters = @(
      [ordered]@{
        name = "q"
        in = "query"
        required = $true
        schema = [ordered]@{
          type = "string"
          minLength = 2
          description = "Zoektekst, bv. 'Belle Banne U 800 frame RVS'"
          title = "Q"
        }
        description = "Zoektekst, bv. 'Belle Banne U 800 frame RVS'"
      },
      [ordered]@{
        name = "limit"
        in = "query"
        required = $false
        schema = [ordered]@{
          type = "integer"
          maximum = 100
          minimum = 1
          default = 25
          title = "Limit"
        }
      }
    )
    responses = [ordered]@{
      "200" = [ordered]@{
        description = "Successful Response"
        content = [ordered]@{
          "application/json" = [ordered]@{
            schema = [ordered]@{
              '$ref' = "#/components/schemas/GenericObject"
            }
          }
        }
      }
      "422" = [ordered]@{
        description = "Validation Error"
        content = [ordered]@{
          "application/json" = [ordered]@{
            schema = [ordered]@{
              '$ref' = "#/components/schemas/HTTPValidationError"
            }
          }
        }
      }
    }
    "x-openai-isConsequential" = $false
  }
}

if ($json.paths.PSObject.Properties.Name -contains $productSearchRoute) {
  $json.paths.$productSearchRoute = $productSearchObject
} else {
  $json.paths | Add-Member -MemberType NoteProperty -Name $productSearchRoute -Value $productSearchObject
}

# ------------------------------------------------------------
# Route 2: /technical/context
# ------------------------------------------------------------
$technicalContextRoute = "/technical/context"

$technicalContextObject = [ordered]@{
  get = [ordered]@{
    tags = @("technical")
    summary = "Get Technical Context"
    description = "Haalt technische kennisbankcontext op voor transportbanden, trommels, rollen, lagers, FAT, normen en RFQ-beoordeling."
    operationId = "get_technical_context_technical_context_get"
    parameters = @(
      [ordered]@{
        name = "q"
        in = "query"
        required = $true
        schema = [ordered]@{
          type = "string"
          minLength = 2
          title = "Q"
        }
      },
      [ordered]@{
        name = "topic_group"
        in = "query"
        required = $false
        schema = [ordered]@{
          anyOf = @(
            [ordered]@{ type = "string" },
            [ordered]@{ type = "null" }
          )
          title = "Topic Group"
        }
      },
      [ordered]@{
        name = "source_code"
        in = "query"
        required = $false
        schema = [ordered]@{
          anyOf = @(
            [ordered]@{ type = "string" },
            [ordered]@{ type = "null" }
          )
          title = "Source Code"
        }
      },
      [ordered]@{
        name = "item_type"
        in = "query"
        required = $false
        schema = [ordered]@{
          anyOf = @(
            [ordered]@{ type = "string" },
            [ordered]@{ type = "null" }
          )
          title = "Item Type"
        }
      },
      [ordered]@{
        name = "limit"
        in = "query"
        required = $false
        schema = [ordered]@{
          type = "integer"
          maximum = 100
          minimum = 1
          default = 20
          title = "Limit"
        }
      }
    )
    responses = [ordered]@{
      "200" = [ordered]@{
        description = "Successful Response"
        content = [ordered]@{
          "application/json" = [ordered]@{
            schema = [ordered]@{
              '$ref' = "#/components/schemas/GenericObject"
            }
          }
        }
      }
      "422" = [ordered]@{
        description = "Validation Error"
        content = [ordered]@{
          "application/json" = [ordered]@{
            schema = [ordered]@{
              '$ref' = "#/components/schemas/HTTPValidationError"
            }
          }
        }
      }
    }
    "x-openai-isConsequential" = $false
  }
}

if ($json.paths.PSObject.Properties.Name -contains $technicalContextRoute) {
  $json.paths.$technicalContextRoute = $technicalContextObject
} else {
  $json.paths | Add-Member -MemberType NoteProperty -Name $technicalContextRoute -Value $technicalContextObject
}

# ------------------------------------------------------------
# Wegschrijven en valideren
# ------------------------------------------------------------
$json | ConvertTo-Json -Depth 100 | Out-File $path -Encoding utf8

Get-Content $path -Raw | ConvertFrom-Json | Out-Null

Write-Host "OpenAPI bijgewerkt en geldig."
Write-Host "Backup staat op: $backup"
Write-Host ""
Write-Host "Toegevoegde/gecontroleerde routes:"
Write-Host $productSearchRoute
Write-Host $technicalContextRoute